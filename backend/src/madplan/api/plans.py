"""Madplanen: dage, retter, rester, ønskeliste og "har hjemme" pr. linje."""

from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..models import Plan, PlanLineState, PlanMeal, Recipe, RecipeIngredient, WishlistItem
from ..planning import MULTIPLIERS, scale
from .deps import CurrentUser, DbSession
from .recipes import image_url, ingredient_ref
from .schemas import IngredientRef

router = APIRouter(prefix="/api")

Kind = Literal["opskrift", "fritekst", "rester"]
LineStateValue = Literal["hjemme", "rest"]


# --- JSON-formater -------------------------------------------------------------

class RecipeBrief(BaseModel):
    id: int
    title: str
    servings: int | None
    image_url: str | None


class MealRef(BaseModel):
    id: int
    date: date
    title: str
    multiplier: float


class MealLine(BaseModel):
    line_id: int
    group: str
    raw: str
    quantity: float | None
    quantity_max: float | None
    unit: str | None
    item: str
    note: str | None
    ingredient: IngredientRef | None
    is_main: bool
    state: LineStateValue | None


class MealOut(BaseModel):
    id: int
    date: date
    for_child: bool
    kind: Kind
    title: str
    recipe: RecipeBrief | None
    text: str
    multiplier: float
    leftover_from: MealRef | None
    # Retten bruger rest fra en ret, der ikke er sat til ×2.
    suggest_double: bool
    lines: list[MealLine]


class DayOut(BaseModel):
    date: date
    meal: MealOut | None
    child: MealOut | None


class WishOut(BaseModel):
    id: int
    recipe: RecipeBrief | None
    text: str
    title: str


class PlanBrief(BaseModel):
    id: int
    start_date: date
    end_date: date


class PlanOut(PlanBrief):
    days: list[DayOut]
    wishlist: list[WishOut]


class PlanIn(BaseModel):
    start_date: date
    days: int = Field(7, ge=1, le=14)


class SlotIn(BaseModel):
    date: date
    for_child: bool = False
    kind: Kind
    recipe_id: int | None = None
    text: str = Field("", max_length=200)
    leftover_from_id: int | None = None
    multiplier: float = 1.0


class MealPatch(BaseModel):
    multiplier: float | None = None
    text: str | None = Field(None, max_length=200)
    # Kun for opskrifter: den ret, resten kommer fra. null fjerner koblingen.
    leftover_from_id: int | None = None


class MoveIn(BaseModel):
    date: date
    for_child: bool = False


class LineStateIn(BaseModel):
    state: LineStateValue | None


class WishIn(BaseModel):
    recipe_id: int | None = None
    text: str = Field("", max_length=200)


# --- Opbygning af svar -----------------------------------------------------------

def _end(plan: Plan) -> date:
    return plan.start_date + timedelta(days=plan.days - 1)


def _brief(r: Recipe | None) -> RecipeBrief | None:
    if r is None:
        return None
    return RecipeBrief(id=r.id, title=r.title, servings=r.servings, image_url=image_url(r))


def meal_title(meal: PlanMeal) -> str:
    if meal.kind == "opskrift":
        return meal.recipe.title if meal.recipe else "Slettet opskrift"
    if meal.kind == "rester":
        return f"Rester: {meal_title(meal.leftover_from)}" if meal.leftover_from else "Rester"
    return meal.text


def _meal_out(meal: PlanMeal) -> MealOut:
    states = {s.line_id: s.state for s in meal.line_states}
    lines = []
    if meal.kind == "opskrift" and meal.recipe:
        for l in meal.recipe.ingredients:
            lines.append(MealLine(
                line_id=l.id, group=l.group, raw=l.raw,
                quantity=scale(l.quantity, l.unit, meal.multiplier),
                quantity_max=scale(l.quantity_max, l.unit, meal.multiplier),
                unit=l.unit, item=l.item, note=l.note, ingredient=ingredient_ref(l.ingredient),
                is_main=l.is_main, state=states.get(l.id),
            ))
    src = meal.leftover_from
    return MealOut(
        id=meal.id, date=meal.date, for_child=meal.for_child, kind=meal.kind, title=meal_title(meal),
        recipe=_brief(meal.recipe), text=meal.text, multiplier=meal.multiplier,
        leftover_from=MealRef(id=src.id, date=src.date, title=meal_title(src), multiplier=src.multiplier)
        if src else None,
        suggest_double=bool(src and src.kind == "opskrift" and src.multiplier < 2),
        lines=lines,
    )


def _wish_title(w: WishlistItem) -> str:
    return w.recipe.title if w.recipe else w.text


def plan_out(plan: Plan) -> PlanOut:
    by_slot = {(m.date, m.for_child): m for m in plan.meals}
    days = []
    for i in range(plan.days):
        d = plan.start_date + timedelta(days=i)
        main, child = by_slot.get((d, False)), by_slot.get((d, True))
        days.append(DayOut(date=d, meal=_meal_out(main) if main else None, child=_meal_out(child) if child else None))
    return PlanOut(
        id=plan.id, start_date=plan.start_date, end_date=_end(plan), days=days,
        wishlist=[WishOut(id=w.id, recipe=_brief(w.recipe), text=w.text, title=_wish_title(w)) for w in plan.wishlist],
    )


def load_plan(session: Session, plan_id: int) -> Plan:
    session.expire_all()
    plan = session.scalar(
        select(Plan).where(Plan.id == plan_id).options(
            selectinload(Plan.meals).selectinload(PlanMeal.recipe).selectinload(Recipe.ingredients)
            .selectinload(RecipeIngredient.ingredient),
            selectinload(Plan.meals).selectinload(PlanMeal.line_states),
            selectinload(Plan.meals).selectinload(PlanMeal.leftover_from).selectinload(PlanMeal.recipe),
            selectinload(Plan.wishlist).selectinload(WishlistItem.recipe),
        )
    )
    if plan is None:
        raise HTTPException(status_code=404, detail="Planen findes ikke")
    return plan


def _meal(session: Session, meal_id: int) -> PlanMeal:
    meal = session.get(PlanMeal, meal_id)
    if meal is None:
        raise HTTPException(status_code=404, detail="Retten findes ikke")
    return meal


# --- Kontrol ---------------------------------------------------------------------

def _check_date(plan: Plan, d: date) -> None:
    if not plan.start_date <= d <= _end(plan):
        raise HTTPException(status_code=422, detail="Datoen ligger uden for planen")


def _check_multiplier(m: float) -> None:
    if m not in MULTIPLIERS:
        raise HTTPException(status_code=422, detail="Gange skal være ½, 1 eller 2")


def _check_recipe(session: Session, recipe_id: int | None) -> Recipe:
    recipe = session.get(Recipe, recipe_id) if recipe_id else None
    if recipe is None:
        raise HTTPException(status_code=422, detail="Vælg en opskrift")
    return recipe


def _check_leftover_source(session: Session, plan: Plan, source_id: int | None, d: date) -> PlanMeal:
    src = session.get(PlanMeal, source_id) if source_id else None
    if src is None or src.plan_id != plan.id or src.kind != "opskrift":
        raise HTTPException(status_code=422, detail="Vælg den ret, resten kommer fra")
    if src.date >= d:
        raise HTTPException(status_code=422, detail="Resten skal komme fra en tidligere dag")
    return src


def _detach(plan: Plan, removed: PlanMeal) -> None:
    """Retter, der brugte rest fra `removed`, mister koblingen og rest-markeringerne."""
    for m in plan.meals:
        if m.leftover_from is removed:
            m.leftover_from = None
            m.line_states = [s for s in m.line_states if s.state != "rest"]


def _clear_slot(session: Session, plan: Plan, d: date, for_child: bool) -> None:
    for m in list(plan.meals):
        if m.date == d and m.for_child == for_child:
            _detach(plan, m)
            plan.meals.remove(m)
    session.flush()


# --- Planer -----------------------------------------------------------------------

@router.get("/plans")
def list_plans(session: DbSession, _: CurrentUser) -> list[PlanBrief]:
    plans = session.scalars(select(Plan).order_by(Plan.start_date.desc()))
    return [PlanBrief(id=p.id, start_date=p.start_date, end_date=_end(p)) for p in plans]


@router.get("/plans/current")
def current_plan(session: DbSession, _: CurrentUser, today: date | None = None) -> PlanOut:
    """Planen, der dækker i dag. Ellers den næste, ellers den seneste."""
    today = today or date.today()
    plans = session.scalars(select(Plan).order_by(Plan.start_date)).all()
    if not plans:
        raise HTTPException(status_code=404, detail="Ingen madplan endnu")
    covering = [p for p in plans if p.start_date <= today <= _end(p)]
    upcoming = [p for p in plans if p.start_date > today]
    chosen = covering[-1] if covering else upcoming[0] if upcoming else plans[-1]
    return plan_out(load_plan(session, chosen.id))


@router.post("/plans", status_code=201)
def create_plan(body: PlanIn, session: DbSession, _: CurrentUser) -> PlanOut:
    end = body.start_date + timedelta(days=body.days - 1)
    for p in session.scalars(select(Plan)):
        if p.start_date <= end and body.start_date <= _end(p):
            raise HTTPException(
                status_code=409,
                detail={"message": f"Overlapper planen fra {p.start_date:%d/%m}", "id": p.id},
            )
    plan = Plan(start_date=body.start_date, days=body.days)
    session.add(plan)
    session.commit()
    return plan_out(load_plan(session, plan.id))


@router.get("/plans/{plan_id}")
def get_plan(plan_id: int, session: DbSession, _: CurrentUser) -> PlanOut:
    return plan_out(load_plan(session, plan_id))


@router.delete("/plans/{plan_id}", status_code=204)
def delete_plan(plan_id: int, session: DbSession, _: CurrentUser) -> None:
    session.delete(load_plan(session, plan_id))
    session.commit()


# --- Retter -----------------------------------------------------------------------

@router.put("/plans/{plan_id}/slots")
def set_slot(plan_id: int, body: SlotIn, session: DbSession, _: CurrentUser) -> PlanOut:
    """Sæt retten på en dag (erstatter en eventuel ret, der står der)."""
    plan = load_plan(session, plan_id)
    _check_date(plan, body.date)
    _check_multiplier(body.multiplier)
    meal = PlanMeal(date=body.date, for_child=body.for_child, kind=body.kind, multiplier=body.multiplier)
    if body.kind == "opskrift":
        meal.recipe = _check_recipe(session, body.recipe_id)
    elif body.kind == "fritekst":
        meal.text = body.text.strip()
        if not meal.text:
            raise HTTPException(status_code=422, detail="Skriv hvad I skal have")
    else:
        meal.leftover_from = _check_leftover_source(session, plan, body.leftover_from_id, body.date)
        meal.multiplier = 1.0
    _clear_slot(session, plan, body.date, body.for_child)
    plan.meals.append(meal)
    session.commit()
    return plan_out(load_plan(session, plan.id))


@router.patch("/meals/{meal_id}")
def update_meal(meal_id: int, body: MealPatch, session: DbSession, _: CurrentUser) -> PlanOut:
    meal = _meal(session, meal_id)
    if body.multiplier is not None:
        _check_multiplier(body.multiplier)
        meal.multiplier = body.multiplier
    if body.text is not None and meal.kind == "fritekst":
        if not body.text.strip():
            raise HTTPException(status_code=422, detail="Skriv hvad I skal have")
        meal.text = body.text.strip()
    if "leftover_from_id" in body.model_fields_set:
        if meal.kind != "opskrift":
            raise HTTPException(status_code=422, detail="Kun opskrifter kan bruge rest")
        if body.leftover_from_id is None:
            meal.leftover_from = None
            # Uden kilde dækker resten ikke længere noget.
            meal.line_states = [s for s in meal.line_states if s.state != "rest"]
        else:
            meal.leftover_from = _check_leftover_source(session, meal.plan, body.leftover_from_id, meal.date)
    session.commit()
    return plan_out(load_plan(session, meal.plan_id))


@router.post("/meals/{meal_id}/move")
def move_meal(meal_id: int, body: MoveIn, session: DbSession, _: CurrentUser) -> PlanOut:
    """Flyt en ret til en anden dag. Står der allerede en ret, byttes de."""
    meal = _meal(session, meal_id)
    plan = meal.plan
    _check_date(plan, body.date)
    other = next((m for m in plan.meals if m.date == body.date and m.for_child == body.for_child), None)
    if other is meal:
        return plan_out(load_plan(session, plan.id))
    old_date, old_child = meal.date, meal.for_child
    # Midlertidig plads, så unik-begrænsningen ikke rammer under byttet.
    meal.date = date(1900, 1, 1)
    session.flush()
    if other:
        other.date, other.for_child = old_date, old_child
        session.flush()
    meal.date, meal.for_child = body.date, body.for_child
    session.flush()
    # En rest kan ikke komme fra samme eller en senere dag.
    for m in plan.meals:
        if m.leftover_from and m.leftover_from.date >= m.date:
            if m.kind == "opskrift":
                m.line_states = [s for s in m.line_states if s.state != "rest"]
            m.leftover_from = None
    session.commit()
    return plan_out(load_plan(session, plan.id))


@router.delete("/meals/{meal_id}")
def delete_meal(meal_id: int, session: DbSession, _: CurrentUser) -> PlanOut:
    meal = _meal(session, meal_id)
    plan = meal.plan
    _detach(plan, meal)
    plan.meals.remove(meal)
    session.commit()
    return plan_out(load_plan(session, plan.id))


@router.put("/meals/{meal_id}/lines/{line_id}")
def set_line_state(meal_id: int, line_id: int, body: LineStateIn, session: DbSession, _: CurrentUser) -> PlanOut:
    """Markér en ingredienslinje som "har hjemme" eller "dækket af rest"."""
    meal = _meal(session, meal_id)
    if meal.kind != "opskrift" or not meal.recipe or line_id not in {l.id for l in meal.recipe.ingredients}:
        raise HTTPException(status_code=404, detail="Linjen hører ikke til retten")
    if body.state == "rest" and not meal.leftover_from:
        raise HTTPException(status_code=422, detail="Vælg først, hvilken ret resten kommer fra")
    existing = next((s for s in meal.line_states if s.line_id == line_id), None)
    if body.state is None:
        if existing:
            meal.line_states.remove(existing)
    elif existing:
        existing.state = body.state
    else:
        meal.line_states.append(PlanLineState(line_id=line_id, state=body.state))
    session.commit()
    return plan_out(load_plan(session, meal.plan_id))


# --- Ønskeliste --------------------------------------------------------------------

@router.post("/plans/{plan_id}/wishlist")
def add_wish(plan_id: int, body: WishIn, session: DbSession, _: CurrentUser) -> PlanOut:
    plan = load_plan(session, plan_id)
    if body.recipe_id is not None:
        plan.wishlist.append(WishlistItem(recipe=_check_recipe(session, body.recipe_id)))
    elif body.text.strip():
        plan.wishlist.append(WishlistItem(text=body.text.strip()))
    else:
        raise HTTPException(status_code=422, detail="Vælg en opskrift eller skriv en ret")
    session.commit()
    return plan_out(load_plan(session, plan.id))


def _wish(session: Session, wish_id: int) -> WishlistItem:
    wish = session.get(WishlistItem, wish_id)
    if wish is None:
        raise HTTPException(status_code=404, detail="Ønsket findes ikke")
    return wish


@router.delete("/wishlist/{wish_id}")
def delete_wish(wish_id: int, session: DbSession, _: CurrentUser) -> PlanOut:
    wish = _wish(session, wish_id)
    plan_id = wish.plan_id
    session.delete(wish)
    session.commit()
    return plan_out(load_plan(session, plan_id))


@router.post("/plans/{plan_id}/wishlist/distribute")
def distribute_wishes(plan_id: int, session: DbSession, _: CurrentUser) -> PlanOut:
    """Læg ønskerne på de ledige dage i rækkefølge. Optagne dage røres ikke.
    Ønsker, der ikke er plads til, bliver på listen."""
    plan = load_plan(session, plan_id)
    taken = {m.date for m in plan.meals if not m.for_child}
    free = [plan.start_date + timedelta(days=i) for i in range(plan.days)]
    free = [d for d in free if d not in taken]
    for wish, d in zip(list(plan.wishlist), free):
        plan.meals.append(PlanMeal(
            date=d, for_child=False, multiplier=1.0,
            kind="opskrift" if wish.recipe_id else "fritekst",
            recipe_id=wish.recipe_id, text=wish.text,
        ))
        plan.wishlist.remove(wish)
    session.commit()
    return plan_out(load_plan(session, plan.id))


@router.post("/wishlist/{wish_id}/place")
def place_wish(wish_id: int, body: MoveIn, session: DbSession, user: CurrentUser) -> PlanOut:
    """Læg et ønske på en dag. Ønsket fjernes fra listen."""
    wish = _wish(session, wish_id)
    slot = SlotIn(
        date=body.date, for_child=body.for_child,
        kind="opskrift" if wish.recipe_id else "fritekst",
        recipe_id=wish.recipe_id, text=wish.text,
    )
    plan_id = wish.plan_id
    session.delete(wish)
    session.flush()
    return set_slot(plan_id, slot, session, user)
