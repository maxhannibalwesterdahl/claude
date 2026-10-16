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
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from ..adjustments import load_adjustments, parse_extras
from ..catalog import Catalog
from ..matching import Overlay, ingredient_map, learn_preference
from ..config import local_today
from ..ingredients.matcher import DEPARTMENTS, key as item_key
from ..models import (
    Household,
    HouseholdStaple,
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
from ..shopping import combine, cover
from .deps import CurrentHousehold, DbSession, pantry_ids
from .plans import PlanBrief, meal_title, pick_current

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
    kind: Literal["plan", "extra", "staple"]
    source: Literal["egen", "løbet tør"] | None = None
    # Linjer uden kendt vare (skal tjekkes). For egne varer: ingen vare valgt.
    unknown: bool = False
    # Egne varer: den vare, teksten er koblet til (bestemmer afdelingen)
    ingredient_name: str | None = None
    # Faste varer: teksten, familien skrev (vises som "fast")
    staple: str | None = None


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
    # Planen, der blev vist, da rækken blev krydset af. Mangler den, gælder
    # SyncIn.plan_id (ældre telefoner).
    plan_id: int | None = None


class SyncIn(BaseModel):
    plan_id: int | None = None
    # Den uge, brugeren har valgt at se. Mangler den (eller er planen slettet),
    # svares med den igangværende uge.
    view_plan_id: int | None = None
    # Valideres én ad gangen i sync(): en ugyldig ændring må ikke blokere resten,
    # for telefonen sender ventende ændringer igen, indtil de bliver modtaget.
    changes: list[dict] = Field([], max_length=2000)


# En telefon med et ur, der går foran, må ikke kunne låse en vare for altid.
MAX_CLOCK_AHEAD_MS = 60_000


class ExtraIn(BaseModel):
    text: str = Field("", max_length=200)
    ingredient_id: int | None = None
    source: Literal["egen", "løbet tør"] = "egen"


class ExtraPatch(BaseModel):
    # null = ingen vare (kommer under "Andet")
    ingredient_id: int | None


class StapleOut(BaseModel):
    id: int
    text: str
    quantity: float | None
    unit: str | None
    item: str
    ingredient_id: int | None
    ingredient_name: str | None
    department: str


class StapleIn(BaseModel):
    text: str = Field("", max_length=200)
    # Mangler den, prøves teksten at blive koblet til en vare af sig selv.
    ingredient_id: int | None = None


class StaplePatch(BaseModel):
    text: str | None = Field(None, max_length=200)
    # null = ingen vare (kommer under "Andet"). Mangler feltet, ændres vare ikke.
    ingredient_id: int | None = None


class HomeIn(BaseModel):
    plan_id: int
    key: str
    home: bool


class DepartmentOrderIn(BaseModel):
    order: list[str]


# --- Hvilken plan -----------------------------------------------------------------

def _end(plan: Plan) -> date:
    return plan.start_date + timedelta(days=plan.days - 1)


def own_plan(session: Session, plan_id: int, hh: Household) -> Plan | None:
    """Familiens plan, ellers None (en anden families plan er som en der ikke findes)."""
    return session.scalar(select(Plan).where(Plan.id == plan_id, Plan.household_id == hh.id))


def choose_plan(session: Session, hh: Household, plan_id: int | None, today: date | None = None) -> Plan | None:
    """Den valgte plan, ellers den igangværende uge (som Planlæg)."""
    if plan_id is not None:
        plan = own_plan(session, plan_id, hh)
        if plan is None:
            raise HTTPException(status_code=404, detail="Planen findes ikke")
        return plan
    return pick_current(session, hh.id, today)


# --- Opbygning -------------------------------------------------------------------

def department_order(session: Session, hh: Household) -> list[str]:
    row = session.get(Setting, (hh.id, "departments"))
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


def _plan_parts(session: Session, hh: Household, plan: Plan) -> tuple[dict[str, list[_Part]], dict[str, Ingredient | None], dict[str, str]]:
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
    adjust = load_adjustments(session, hh.id, {m.recipe_id for m in meals if m.recipe_id})
    parsed_extras = parse_extras(session, hh.id, adjust)
    overlay = Overlay.load(session, hh.id)
    ings = ingredient_map(session)
    for meal in meals:
        if not meal.recipe:
            continue
        adj = adjust[meal.recipe.id]
        states = {s.line_id: s.state for s in meal.line_states if s.line_id is not None}
        extra_states = {s.adjustment_id: s.state for s in meal.line_states if s.adjustment_id is not None}
        title = meal_title(meal)
        if meal.multiplier != 1:
            # Linjen vises som i opskriften, så gangen skal fremgå.
            title += " (×½)" if meal.multiplier == 0.5 else f" (×{meal.multiplier:g})"
        for line in meal.recipe.ingredients:
            state = states.get(line.id)
            if state == "rest" or line.id in adj.skip:
                continue
            ing = ings.get(overlay.resolve(line)[0])
            k = f"i:{ing.id}" if ing else f"t:{item_key(line.item)}"
            ingredients[k] = ing
            names.setdefault(k, ing.name if ing else line.item)
            own = adj.quantity.get(line.id)
            q = own if own is not None else (line.quantity_max if line.quantity_max is not None else line.quantity)
            parts[k].append(_Part(scale(q, line.unit, meal.multiplier), line.unit, meal.date, title, line.raw, state))
        # Familiens ekstra linjer ("1 dåse majs") lægges til som almindelige linjer.
        for extra in adj.extras:
            state = extra_states.get(extra.id)
            if state == "rest":
                continue
            p, ing = parsed_extras[extra.id]
            k = f"i:{ing.id}" if ing else f"t:{item_key(p.item)}"
            ingredients[k] = ing
            names.setdefault(k, ing.name if ing else p.item)
            q = p.quantity_max if p.quantity_max is not None else p.quantity
            parts[k].append(_Part(scale(q, p.unit, meal.multiplier), p.unit, meal.date, title, extra.value, state))
    return parts, ingredients, names


def _amounts(parts: list[_Part], ing: Ingredient | None) -> list[AmountOut]:
    combined = combine(
        [(p.quantity, p.unit) for p in parts if p.quantity is not None],
        ing.grams_per_piece if ing else None,
        ing.grams_per_dl if ing else None,
    )
    return [AmountOut(quantity=a.quantity, unit=a.unit) for a in combined]


def plan_extras(session: Session, hh: Household, plan: Plan | None, today: date | None = None) -> list[ShoppingExtra]:
    """Egne varer på planens liste: dem, der er skrevet på den uge.

    En vare, der ikke blev købt, før ugen var slut (eller hvis plan er slettet),
    følger med til den igangværende uge, så den bliver på listen, til den er købt."""
    today = today or local_today()
    current = pick_current(session, hh.id, today)
    extras = session.scalars(
        select(ShoppingExtra)
        .where(ShoppingExtra.household_id == hh.id)
        .options(selectinload(ShoppingExtra.ingredient), selectinload(ShoppingExtra.plan))
        .order_by(ShoppingExtra.id)
    ).all()

    def belongs_to(e: ShoppingExtra) -> Plan | None:
        if e.plan is not None and (e.checked or _end(e.plan) >= today):
            return e.plan
        return current

    return [e for e in extras if belongs_to(e) is plan]


def _staples(session: Session, hh: Household) -> list[HouseholdStaple]:
    return list(session.scalars(
        select(HouseholdStaple).where(HouseholdStaple.household_id == hh.id)
        .options(selectinload(HouseholdStaple.ingredient))
        .order_by(HouseholdStaple.position, HouseholdStaple.id)
    ).all())


def _staple_groups(session: Session, hh: Household) -> dict[str, list[HouseholdStaple]]:
    """Faste varer grupperet efter række-nøgle. Samme vare ("i:<id>") deler række med ugens retter."""
    groups: dict[str, list[HouseholdStaple]] = defaultdict(list)
    for s in _staples(session, hh):
        groups[f"i:{s.ingredient_id}" if s.ingredient_id else f"f:{s.id}"].append(s)
    return groups


def _fixed_pairs(group: list[HouseholdStaple]) -> list[tuple[float | None, str | None]]:
    return [(s.quantity, s.unit) for s in group if s.quantity is not None]


def _staple_text(group: list[HouseholdStaple] | None) -> str | None:
    return ", ".join(s.text for s in group) if group else None


def _item_amounts(buy: list[_Part], group: list[HouseholdStaple] | None, ing: Ingredient | None) -> list[AmountOut]:
    """Mængden på listen: uden faste varer lægges retternes mængder sammen (som før).
    Med en fast vare tæller den største af de to (cover), så de ikke lægges sammen."""
    if not group:
        return _amounts(buy, ing)
    need = [(p.quantity, p.unit) for p in buy if p.quantity is not None]
    covered = cover(_fixed_pairs(group), need,
                    ing.grams_per_piece if ing else None, ing.grams_per_dl if ing else None)
    return [AmountOut(quantity=a.quantity, unit=a.unit) for a in covered]


def build(session: Session, hh: Household, plan: Plan | None, now_ms: int | None = None, today: date | None = None) -> ShoppingOut:
    now_ms = now_ms or int(time.time() * 1000)
    order = department_order(session, hh)
    household_pantry = pantry_ids(session, hh.id)
    items: list[ItemOut] = []
    pantry: list[PantryOut] = []
    home: list[HomeOut] = []

    extras = plan_extras(session, hh, plan, today)
    requested = {e.ingredient_id for e in extras if e.source == "løbet tør" and not e.checked}

    if plan is not None:
        checks = {c.key: c.checked for c in session.scalars(select(ShoppingCheck).where(ShoppingCheck.plan_id == plan.id))}
        parts, ingredients, names = _plan_parts(session, hh, plan)
        fixed = _staple_groups(session, hh)
        for k, ps in parts.items():
            ing = ingredients[k]
            group = fixed.pop(k, None)
            # Familiens basisvarer går til lageret, men en fast vare står altid på listen.
            if group is None and ing is not None and ing.id in household_pantry:
                pantry.append(PantryOut(
                    ingredient_id=ing.id, name=ing.name, amounts=_amounts(ps, ing),
                    days=sorted({p.date for p in ps}), requested=ing.id in requested,
                ))
                continue
            buy = [p for p in ps if p.state != "hjemme"]
            if not buy and group is None:
                home.append(HomeOut(key=k, name=names[k]))
                continue
            items.append(ItemOut(
                key=k, name=names[k], department=ing.department if ing else "andet",
                amounts=_item_amounts(buy, group, ing), unquantified=any(p.quantity is None for p in buy),
                days=sorted({p.date for p in buy}),
                sources=[SourceOut(date=p.date, meal=p.meal, raw=p.raw) for p in sorted(buy, key=lambda p: p.date)],
                checked=checks.get(k, False), kind="plan", unknown=ing is None, staple=_staple_text(group),
            ))
        # Faste varer, som ugens retter slet ikke bruger.
        for k, group in fixed.items():
            ing = group[0].ingredient
            items.append(ItemOut(
                key=k, name=ing.name if ing else group[0].item, department=ing.department if ing else "andet",
                amounts=_item_amounts([], group, ing), unquantified=False, days=[], sources=[],
                checked=checks.get(k, False), kind="staple", unknown=ing is None,
                ingredient_name=ing.name if ing else None, staple=_staple_text(group),
            ))

    for e in extras:
        if e.checked and now_ms - e.updated_ms > EXTRA_VISIBLE_MS:
            continue
        items.append(ItemOut(
            key=f"e:{e.id}", name=e.text, department=e.ingredient.department if e.ingredient else "andet",
            amounts=[], unquantified=False, days=[], sources=[], checked=e.checked, kind="extra", source=e.source,
            unknown=e.ingredient is None, ingredient_name=e.ingredient.name if e.ingredient else None,
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


# --- Faste varer -------------------------------------------------------------------

def _parse_staple(session: Session, hh: Household, text: str) -> tuple[float | None, str | None, str, int | None]:
    """Mængde, enhed, vare og den vare, teksten passer til (kun en sikker match)."""
    p = Catalog(session, hh.id).parse(text)
    quantity = p.quantity_max if p.quantity_max is not None else p.quantity
    auto = p.ingredient_id if p.match_status == "sikker" else None
    return quantity, p.unit, p.item or text, auto


def _ingredient(session: Session, ingredient_id: int | None) -> Ingredient | None:
    if ingredient_id is None:
        return None
    ing = session.get(Ingredient, ingredient_id)
    if ing is None:
        raise HTTPException(status_code=404, detail="Varen findes ikke")
    return ing


def _staple_out(s: HouseholdStaple) -> StapleOut:
    ing = s.ingredient
    return StapleOut(
        id=s.id, text=s.text, quantity=s.quantity, unit=s.unit, item=s.item, ingredient_id=s.ingredient_id,
        ingredient_name=ing.name if ing else None, department=ing.department if ing else "andet",
    )


def _own_staple(session: Session, staple_id: int, hh: Household) -> HouseholdStaple:
    staple = session.scalar(select(HouseholdStaple).where(
        HouseholdStaple.id == staple_id, HouseholdStaple.household_id == hh.id))
    if staple is None:
        raise HTTPException(status_code=404, detail="Varen findes ikke")
    return staple


@router.get("/staples")
def get_staples(session: DbSession, hh: CurrentHousehold) -> list[StapleOut]:
    return [_staple_out(s) for s in _staples(session, hh)]


@router.post("/staples", status_code=201)
def add_staple(body: StapleIn, session: DbSession, hh: CurrentHousehold) -> StapleOut:
    """Fast vare ("2 l mælk"). Kommer på hver uges liste, til den tages af listen igen."""
    text = " ".join(body.text.split())
    if not text:
        raise HTTPException(status_code=422, detail="Skriv en vare")
    quantity, unit, item, auto = _parse_staple(session, hh, text)
    ing = _ingredient(session, body.ingredient_id if body.ingredient_id is not None else auto)
    last = session.scalar(select(func.max(HouseholdStaple.position)).where(HouseholdStaple.household_id == hh.id))
    staple = HouseholdStaple(
        household_id=hh.id, text=text, quantity=quantity, unit=unit, item=item, ingredient=ing,
        position=0 if last is None else last + 1,
    )
    session.add(staple)
    if body.ingredient_id is not None and ing is not None:
        _learn_from_extra(session, hh, text, ing)
    session.commit()
    return _staple_out(staple)


@router.patch("/staples/{staple_id}")
def update_staple(staple_id: int, body: StaplePatch, session: DbSession, hh: CurrentHousehold) -> StapleOut:
    staple = _own_staple(session, staple_id, hh)
    chosen = "ingredient_id" in body.model_fields_set
    if body.text is not None:
        # Ny tekst: læs den igen. Mangler en vare, prøves teksten at finde sin egen.
        text = " ".join(body.text.split())
        if not text:
            raise HTTPException(status_code=422, detail="Skriv en vare")
        quantity, unit, item, auto = _parse_staple(session, hh, text)
        staple.text, staple.quantity, staple.unit, staple.item = text, quantity, unit, item
        staple.ingredient = _ingredient(session, body.ingredient_id if chosen else auto)
    elif chosen:
        staple.ingredient = _ingredient(session, body.ingredient_id)
    if chosen and staple.ingredient is not None:
        _learn_from_extra(session, hh, staple.text, staple.ingredient)
    session.commit()
    return _staple_out(staple)


@router.delete("/staples/{staple_id}", status_code=204)
def delete_staple(staple_id: int, session: DbSession, hh: CurrentHousehold) -> None:
    session.delete(_own_staple(session, staple_id, hh))
    session.commit()


# --- Ruter -------------------------------------------------------------------------

@router.get("/shopping")
def get_shopping(session: DbSession, hh: CurrentHousehold, plan_id: int | None = None, today: date | None = None) -> ShoppingOut:
    return build(session, hh, choose_plan(session, hh, plan_id, today), today=today)


@router.post("/shopping/sync")
def sync(body: SyncIn, session: DbSession, hh: CurrentHousehold, today: date | None = None) -> ShoppingOut:
    """Modtag afkrydsninger (evt. lavet offline). Seneste ændring pr. række vinder.

    Ændringerne gemmes på den plan, telefonen viste, da de blev lavet. Svaret er
    den valgte uge, ellers den igangværende, så telefonen følger med, når en plan
    slettes, eller når en ny uge begynder."""
    target = own_plan(session, body.plan_id, hh) if body.plan_id is not None else choose_plan(session, hh, None, today)
    plans: dict[int, Plan | None] = {}
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
            extra = None
            if ch.key[2:].isdigit():
                extra = session.scalar(select(ShoppingExtra).where(
                    ShoppingExtra.id == int(ch.key[2:]), ShoppingExtra.household_id == hh.id))
            if extra and ch.ts > extra.updated_ms:
                extra.checked, extra.updated_ms = ch.checked, ch.ts
        elif ch.key[:2] in ("i:", "t:", "f:"):
            if ch.plan_id is None:
                plan = target
            else:
                if ch.plan_id not in plans:
                    plans[ch.plan_id] = own_plan(session, ch.plan_id, hh)
                plan = plans[ch.plan_id]
            if plan is None:
                continue
            row = session.scalar(select(ShoppingCheck).where(ShoppingCheck.plan_id == plan.id, ShoppingCheck.key == ch.key))
            if row is None:
                try:
                    with session.begin_nested():
                        session.add(ShoppingCheck(plan_id=plan.id, key=ch.key, checked=ch.checked, updated_ms=ch.ts))
                except IntegrityError:
                    # En anden telefon nåede først: den seneste ændring vinder stadig.
                    row = session.scalar(select(ShoppingCheck).where(ShoppingCheck.plan_id == plan.id, ShoppingCheck.key == ch.key))
                    if row is not None and ch.ts > row.updated_ms:
                        row.checked, row.updated_ms = ch.checked, ch.ts
            elif ch.ts > row.updated_ms:
                row.checked, row.updated_ms = ch.checked, ch.ts
    session.commit()
    view = own_plan(session, body.view_plan_id, hh) if body.view_plan_id is not None else None
    return build(session, hh, view or choose_plan(session, hh, None, today), today=today)


@router.post("/shopping/extras", status_code=201)
def add_extra(body: ExtraIn, session: DbSession, hh: CurrentHousehold, plan_id: int | None = None, today: date | None = None) -> ShoppingOut:
    """Egen vare ("2 pk bleer") eller "løbet tør" for en basisvare.

    Varen kommer på listen for den uge, der vises (`plan_id`), ikke på de andre uger.

    Egne varer kobles til en vare i ingredienstabellen, så de sorteres efter
    afdeling. Frontend spørger brugeren (vare-vælgeren), når appen ikke er sikker,
    og sender så `ingredient_id`. Valget huskes som alias ("pampers" -> bleer).
    """
    text = " ".join(body.text.split())
    plan = choose_plan(session, hh, plan_id, today)
    if body.ingredient_id is not None:
        ing = session.get(Ingredient, body.ingredient_id)
        if ing is None:
            raise HTTPException(status_code=404, detail="Varen findes ikke")
        if body.source == "løbet tør":
            already = any(e.ingredient_id == ing.id and not e.checked for e in plan_extras(session, hh, plan, today))
            if not already:
                session.add(ShoppingExtra(household_id=hh.id, text=ing.name, ingredient=ing, source="løbet tør", plan=plan))
        elif not _already_on_list(session, hh, plan, text or ing.name, today):
            session.add(ShoppingExtra(household_id=hh.id, text=text or ing.name, ingredient=ing, source="egen", plan=plan))
            if text:
                _learn_from_extra(session, hh, text, ing)
    else:
        if not text:
            raise HTTPException(status_code=422, detail="Skriv en vare")
        # Kendt vare? Så kommer den under den rigtige afdeling.
        found = Catalog(session, hh.id).parse(text)
        ing = session.get(Ingredient, found.ingredient_id) if found.match_status == "sikker" else None
        if not _already_on_list(session, hh, plan, text, today):
            session.add(ShoppingExtra(household_id=hh.id, text=text, ingredient=ing, source="egen", plan=plan))
    session.commit()
    return build(session, hh, plan, today=today)


def _already_on_list(session: Session, hh: Household, plan: Plan | None, text: str, today: date | None) -> bool:
    """Dobbeltklik på "Tilføj": den samme egne vare, der ikke er købt, kommer kun på én gang."""
    want = text.casefold()
    return any(e.source == "egen" and not e.checked and e.text.casefold() == want
               for e in plan_extras(session, hh, plan, today))


def _extra(session: Session, extra_id: int, hh: Household) -> ShoppingExtra:
    extra = session.scalar(select(ShoppingExtra).where(ShoppingExtra.id == extra_id, ShoppingExtra.household_id == hh.id))
    if extra is None:
        raise HTTPException(status_code=404, detail="Varen findes ikke")
    return extra


def _learn_from_extra(session: Session, hh: Household, text: str, ing: Ingredient) -> None:
    """Husk familiens valg: varenavnet fra teksten ("2 pk pampers" -> "pampers") bliver
    familiens eget navn for varen, ligesom når en opskriftslinje bekræftes."""
    item = Catalog(session, hh.id).parse(text).item
    if item:
        learn_preference(session, hh.id, item, ing)


@router.patch("/shopping/extras/{extra_id}")
def update_extra(extra_id: int, body: ExtraPatch, session: DbSession, hh: CurrentHousehold,
                 plan_id: int | None = None, today: date | None = None) -> ShoppingOut:
    """Skift den vare, en egen vare er koblet til (fx fra "Andet" til bleer)."""
    extra = _extra(session, extra_id, hh)
    ing = session.get(Ingredient, body.ingredient_id) if body.ingredient_id is not None else None
    if body.ingredient_id is not None and ing is None:
        raise HTTPException(status_code=404, detail="Varen findes ikke")
    extra.ingredient = ing
    if ing is not None and extra.source == "egen":
        _learn_from_extra(session, hh, extra.text, ing)
    session.commit()
    return build(session, hh, choose_plan(session, hh, plan_id, today), today=today)


@router.delete("/shopping/extras/{extra_id}")
def delete_extra(extra_id: int, session: DbSession, hh: CurrentHousehold, plan_id: int | None = None, today: date | None = None) -> ShoppingOut:
    extra = _extra(session, extra_id, hh)
    session.delete(extra)
    session.commit()
    return build(session, hh, choose_plan(session, hh, plan_id, today), today=today)


@router.post("/shopping/home")
def set_home(body: HomeIn, session: DbSession, hh: CurrentHousehold) -> ShoppingOut:
    """"Har hjemme" for en vare: markerer alle dens linjer i planen (eller fjerner
    markeringen igen). Linjer dækket af rest røres ikke."""
    plan = choose_plan(session, hh, body.plan_id)
    meals = session.scalars(
        select(PlanMeal).where(PlanMeal.plan_id == plan.id, PlanMeal.kind == "opskrift").options(
            selectinload(PlanMeal.recipe).selectinload(Recipe.ingredients), selectinload(PlanMeal.line_states))
    ).all()
    overlay = Overlay.load(session, hh.id)
    adjust = load_adjustments(session, hh.id, {m.recipe_id for m in meals if m.recipe_id})
    parsed_extras = parse_extras(session, hh.id, adjust)
    for meal in meals:
        if not meal.recipe:
            continue
        adj = adjust[meal.recipe.id]
        states = {s.line_id: s for s in meal.line_states if s.line_id is not None}
        extra_states = {s.adjustment_id: s for s in meal.line_states if s.adjustment_id is not None}
        for line in meal.recipe.ingredients:
            ing_id = overlay.resolve(line)[0]
            k = f"i:{ing_id}" if ing_id else f"t:{item_key(line.item)}"
            if k != body.key:
                continue
            st = states.get(line.id)
            if body.home and st is None:
                meal.line_states.append(PlanLineState(line_id=line.id, state="hjemme"))
            elif not body.home and st is not None and st.state == "hjemme":
                meal.line_states.remove(st)
        for extra in adj.extras:
            p, ing = parsed_extras[extra.id]
            k = f"i:{ing.id}" if ing else f"t:{item_key(p.item)}"
            if k != body.key:
                continue
            st = extra_states.get(extra.id)
            if body.home and st is None:
                meal.line_states.append(PlanLineState(adjustment_id=extra.id, state="hjemme"))
            elif not body.home and st is not None and st.state == "hjemme":
                meal.line_states.remove(st)
    session.commit()
    return build(session, hh, plan)


@router.get("/settings/departments")
def get_department_order(session: DbSession, hh: CurrentHousehold) -> list[DepartmentOut]:
    return [DepartmentOut(code=c, name=DEPARTMENTS[c]) for c in department_order(session, hh)]


@router.put("/settings/departments")
def set_department_order(body: DepartmentOrderIn, session: DbSession, hh: CurrentHousehold) -> list[DepartmentOut]:
    if sorted(body.order) != sorted(DEPARTMENTS):
        raise HTTPException(status_code=422, detail="Rækkefølgen skal indeholde alle afdelinger")
    row = session.get(Setting, (hh.id, "departments")) or Setting(household_id=hh.id, key="departments")
    row.value = json.dumps(body.order)
    session.add(row)
    session.commit()
    return get_department_order(session, hh)
