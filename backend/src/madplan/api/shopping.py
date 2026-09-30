"""Indkøbslisten: samlet fra madplanen plus egne varer. Se docs/SPEC.md §3.5-3.6.

Afkrydsning virker offline på telefonen. Ændringer sendes med klientens
tidspunkt, og den seneste ændring pr. række vinder (samme metode som testet i
fase 0).
"""

import json
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..catalog import Catalog
from ..ingredients.matcher import DEPARTMENTS, key as item_key
from ..config import local_today
from ..models import (
    Ingredient,
    Plan,
    PlanLineState,
    PlanMeal,
    Recipe,
    RecipeIngredient,
    Setting,
    ShoppingCheck,
    ShoppingExtra,
)
from ..planning import scale
from ..shopping import combine
from .deps import CurrentUser, DbSession
from .plans import PlanBrief, meal_title

router = APIRouter(prefix="/api")

# Købte egne varer vises (overstreget) så længe efter, de er krydset af.
EXTRA_VISIBLE_MS = 12 * 3600 * 1000


# --- JSON-formater -------------------------------------------------------------

class AmountOut(BaseModel):
    quantity: float
    unit: str | None


class SourceOut(BaseModel):
    date: date
    meal: str
    raw: str


class ItemOut(BaseModel):
    key: str
    name: str
    department: str
    amounts: list[AmountOut]
    # En eller flere linjer uden mængde ("salt og peber", "persille")
    unquantified: bool
    days: list[date]
    sources: list[SourceOut]
    checked: bool
    kind: Literal["plan", "extra"]
    source: Literal["egen", "løbet tør"] | None = None
    # Linjer uden kendt vare (skal tjekkes)
    unknown: bool = False


class PantryOut(BaseModel):
    ingredient_id: int
    name: str
    amounts: list[AmountOut]
    days: list[date]
    requested: bool


class HomeOut(BaseModel):
    key: str
    name: str


class DepartmentOut(BaseModel):
    code: str
    name: str


class ShoppingOut(BaseModel):
    plan: PlanBrief | None
    departments: list[DepartmentOut]
    items: list[ItemOut]
    pantry: list[PantryOut]
    home: list[HomeOut]
    server_ms: int


class Change(BaseModel):
    key: str = Field(max_length=300)
    checked: bool
    ts: int  # klientens tidspunkt i ms (rettet for urforskel, se frontend)


class SyncIn(BaseModel):
    plan_id: int | None = None
    # Valideres én ad gangen i sync(): en ugyldig ændring må ikke blokere resten,
    # for telefonen sender ventende ændringer igen, indtil de bliver modtaget.
    changes: list[dict] = Field([], max_length=2000)


# En telefon med et ur, der går foran, må ikke kunne låse en vare for altid.
MAX_CLOCK_AHEAD_MS = 60_000


class ExtraIn(BaseModel):
    text: str = Field("", max_length=200)
    ingredient_id: int | None = None
    source: Literal["egen", "løbet tør"] = "egen"


class HomeIn(BaseModel):
    plan_id: int
    key: str
    home: bool


class DepartmentOrderIn(BaseModel):
    order: list[str]


# --- Hvilken plan -----------------------------------------------------------------

def _end(plan: Plan) -> date:
    return plan.start_date + timedelta(days=plan.days - 1)


def choose_plan(session: Session, plan_id: int | None, today: date | None = None) -> Plan | None:
    """Næste indkøb: planen, der starter i dag eller senere. Ellers den igangværende,
    ellers den seneste."""
    if plan_id is not None:
        plan = session.get(Plan, plan_id)
        if plan is None:
            raise HTTPException(status_code=404, detail="Planen findes ikke")
        return plan
    today = today or local_today()
    plans = session.scalars(select(Plan).order_by(Plan.start_date)).all()
    upcoming = [p for p in plans if p.start_date >= today]
    covering = [p for p in plans if p.start_date <= today <= _end(p)]
    return upcoming[0] if upcoming else covering[-1] if covering else plans[-1] if plans else None


# --- Opbygning -------------------------------------------------------------------

def department_order(session: Session) -> list[str]:
    row = session.get(Setting, "departments")
    saved = json.loads(row.value) if row else []
    order = [c for c in saved if c in DEPARTMENTS]
    return order + [c for c in DEPARTMENTS if c not in order]


@dataclass
class _Part:
    quantity: float | None
    unit: str | None
    date: date
    meal: str
    raw: str
    state: str | None


def _plan_parts(session: Session, plan: Plan) -> tuple[dict[str, list[_Part]], dict[str, Ingredient | None], dict[str, str]]:
    """Alle ingredienslinjer i planen, grupperet efter række-nøgle."""
    meals = session.scalars(
        select(PlanMeal).where(PlanMeal.plan_id == plan.id, PlanMeal.kind == "opskrift").options(
            selectinload(PlanMeal.recipe).selectinload(Recipe.ingredients).selectinload(RecipeIngredient.ingredient),
            selectinload(PlanMeal.line_states),
        )
    ).all()
    parts: dict[str, list[_Part]] = defaultdict(list)
    ingredients: dict[str, Ingredient | None] = {}
    names: dict[str, str] = {}
    for meal in meals:
        if not meal.recipe:
            continue
        states = {s.line_id: s.state for s in meal.line_states}
        title = meal_title(meal)
        if meal.multiplier != 1:
            # Linjen vises som i opskriften, så gangen skal fremgå.
            title += " (×½)" if meal.multiplier == 0.5 else f" (×{meal.multiplier:g})"
        for line in meal.recipe.ingredients:
            state = states.get(line.id)
            if state == "rest":
                continue
            ing = line.ingredient
            k = f"i:{ing.id}" if ing else f"t:{item_key(line.item)}"
            ingredients[k] = ing
            names.setdefault(k, ing.name if ing else line.item)
            q = line.quantity_max if line.quantity_max is not None else line.quantity
            parts[k].append(_Part(scale(q, line.unit, meal.multiplier), line.unit, meal.date, title, line.raw, state))
    return parts, ingredients, names


def _amounts(parts: list[_Part], ing: Ingredient | None) -> list[AmountOut]:
    combined = combine(
        [(p.quantity, p.unit) for p in parts if p.quantity is not None],
        ing.grams_per_piece if ing else None,
        ing.grams_per_dl if ing else None,
    )
    return [AmountOut(quantity=a.quantity, unit=a.unit) for a in combined]


def build(session: Session, plan: Plan | None, now_ms: int | None = None) -> ShoppingOut:
    now_ms = now_ms or int(time.time() * 1000)
    order = department_order(session)
    items: list[ItemOut] = []
    pantry: list[PantryOut] = []
    home: list[HomeOut] = []

    extras = session.scalars(
        select(ShoppingExtra).options(selectinload(ShoppingExtra.ingredient)).order_by(ShoppingExtra.id)
    ).all()
    requested = {e.ingredient_id for e in extras if e.source == "løbet tør" and not e.checked}

    if plan is not None:
        checks = {c.key: c.checked for c in session.scalars(select(ShoppingCheck).where(ShoppingCheck.plan_id == plan.id))}
        parts, ingredients, names = _plan_parts(session, plan)
        for k, ps in parts.items():
            ing = ingredients[k]
            if ing is not None and ing.pantry:
                pantry.append(PantryOut(
                    ingredient_id=ing.id, name=ing.name, amounts=_amounts(ps, ing),
                    days=sorted({p.date for p in ps}), requested=ing.id in requested,
                ))
                continue
            buy = [p for p in ps if p.state != "hjemme"]
            if not buy:
                home.append(HomeOut(key=k, name=names[k]))
                continue
            items.append(ItemOut(
                key=k, name=names[k], department=ing.department if ing else "andet",
                amounts=_amounts(buy, ing), unquantified=any(p.quantity is None for p in buy),
                days=sorted({p.date for p in buy}),
                sources=[SourceOut(date=p.date, meal=p.meal, raw=p.raw) for p in sorted(buy, key=lambda p: p.date)],
                checked=checks.get(k, False), kind="plan", unknown=ing is None,
            ))

    for e in extras:
        if e.checked and now_ms - e.updated_ms > EXTRA_VISIBLE_MS:
            continue
        items.append(ItemOut(
            key=f"e:{e.id}", name=e.text, department=e.ingredient.department if e.ingredient else "andet",
            amounts=[], unquantified=False, days=[], sources=[], checked=e.checked, kind="extra", source=e.source,
        ))

    rank = {c: i for i, c in enumerate(order)}
    items.sort(key=lambda i: (rank.get(i.department, 99), i.name.lower()))
    pantry.sort(key=lambda p: p.name)
    home.sort(key=lambda h: h.name)
    return ShoppingOut(
        plan=PlanBrief(id=plan.id, start_date=plan.start_date, end_date=_end(plan)) if plan else None,
        departments=[DepartmentOut(code=c, name=DEPARTMENTS[c]) for c in order],
        items=items, pantry=pantry, home=home, server_ms=now_ms,
    )


# --- Ruter -------------------------------------------------------------------------

@router.get("/shopping")
def get_shopping(session: DbSession, _: CurrentUser, plan_id: int | None = None, today: date | None = None) -> ShoppingOut:
    return build(session, choose_plan(session, plan_id, today))


@router.post("/shopping/sync")
def sync(body: SyncIn, session: DbSession, _: CurrentUser, today: date | None = None) -> ShoppingOut:
    """Modtag afkrydsninger (evt. lavet offline). Seneste ændring pr. række vinder.

    Ændringerne gemmes på den plan, telefonen viste, da de blev lavet. Svaret er
    altid listen til næste indkøb, så telefonen følger med, når en plan slettes,
    eller når næste uges plan oprettes."""
    target = session.get(Plan, body.plan_id) if body.plan_id is not None else choose_plan(session, None, today)
    now_ms = int(time.time() * 1000)
    changes = []
    for raw in body.changes:
        try:
            ch = Change.model_validate(raw)
        except ValueError:
            continue  # ugyldig ændring springes over; resten gemmes
        ch.ts = max(0, min(ch.ts, now_ms + MAX_CLOCK_AHEAD_MS))
        changes.append(ch)
    for ch in changes:
        if ch.key.startswith("e:"):
            extra = session.get(ShoppingExtra, int(ch.key[2:])) if ch.key[2:].isdigit() else None
            if extra and ch.ts > extra.updated_ms:
                extra.checked, extra.updated_ms = ch.checked, ch.ts
        elif target is not None and ch.key[:2] in ("i:", "t:"):
            row = session.scalar(select(ShoppingCheck).where(ShoppingCheck.plan_id == target.id, ShoppingCheck.key == ch.key))
            if row is None:
                session.add(ShoppingCheck(plan_id=target.id, key=ch.key, checked=ch.checked, updated_ms=ch.ts))
            elif ch.ts > row.updated_ms:
                row.checked, row.updated_ms = ch.checked, ch.ts
    session.commit()
    return build(session, choose_plan(session, None, today))


@router.post("/shopping/extras", status_code=201)
def add_extra(body: ExtraIn, session: DbSession, _: CurrentUser, plan_id: int | None = None, today: date | None = None) -> ShoppingOut:
    """Egen vare ("bleer") eller "løbet tør" for en basisvare."""
    if body.ingredient_id is not None:
        ing = session.get(Ingredient, body.ingredient_id)
        if ing is None:
            raise HTTPException(status_code=404, detail="Varen findes ikke")
        already = session.scalar(select(ShoppingExtra).where(
            ShoppingExtra.ingredient_id == ing.id, ShoppingExtra.checked.is_(False)))
        if already is None:
            session.add(ShoppingExtra(text=ing.name, ingredient=ing, source=body.source))
    else:
        text = " ".join(body.text.split())
        if not text:
            raise HTTPException(status_code=422, detail="Skriv en vare")
        # Kendt vare? Så kommer den under den rigtige afdeling.
        found = Catalog(session).parse(text)
        ing = session.get(Ingredient, found.ingredient_id) if found.match_status == "sikker" else None
        session.add(ShoppingExtra(text=text, ingredient=ing, source="egen"))
    session.commit()
    return build(session, choose_plan(session, plan_id, today))


@router.delete("/shopping/extras/{extra_id}")
def delete_extra(extra_id: int, session: DbSession, _: CurrentUser, plan_id: int | None = None, today: date | None = None) -> ShoppingOut:
    extra = session.get(ShoppingExtra, extra_id)
    if extra is None:
        raise HTTPException(status_code=404, detail="Varen findes ikke")
    session.delete(extra)
    session.commit()
    return build(session, choose_plan(session, plan_id, today))


@router.post("/shopping/home")
def set_home(body: HomeIn, session: DbSession, _: CurrentUser) -> ShoppingOut:
    """"Har hjemme" for en vare: markerer alle dens linjer i planen (eller fjerner
    markeringen igen). Linjer dækket af rest røres ikke."""
    plan = choose_plan(session, body.plan_id)
    meals = session.scalars(
        select(PlanMeal).where(PlanMeal.plan_id == plan.id, PlanMeal.kind == "opskrift").options(
            selectinload(PlanMeal.recipe).selectinload(Recipe.ingredients), selectinload(PlanMeal.line_states))
    ).all()
    for meal in meals:
        if not meal.recipe:
            continue
        states = {s.line_id: s for s in meal.line_states}
        for line in meal.recipe.ingredients:
            k = f"i:{line.ingredient_id}" if line.ingredient_id else f"t:{item_key(line.item)}"
            if k != body.key:
                continue
            st = states.get(line.id)
            if body.home and st is None:
                meal.line_states.append(PlanLineState(line_id=line.id, state="hjemme"))
            elif not body.home and st is not None and st.state == "hjemme":
                meal.line_states.remove(st)
    session.commit()
    return build(session, plan)


@router.get("/settings/departments")
def get_department_order(session: DbSession, _: CurrentUser) -> list[DepartmentOut]:
    return [DepartmentOut(code=c, name=DEPARTMENTS[c]) for c in department_order(session)]


@router.put("/settings/departments")
def set_department_order(body: DepartmentOrderIn, session: DbSession, _: CurrentUser) -> list[DepartmentOut]:
    if sorted(body.order) != sorted(DEPARTMENTS):
        raise HTTPException(status_code=422, detail="Rækkefølgen skal indeholde alle afdelinger")
    row = session.get(Setting, "departments") or Setting(key="departments")
    row.value = json.dumps(body.order)
    session.add(row)
    session.commit()
    return get_department_order(session, _)
