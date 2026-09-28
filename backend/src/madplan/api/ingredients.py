from fastapi import APIRouter, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from ..catalog import Catalog
from ..ingredients.matcher import DEPARTMENTS, key
from ..ingredients.parser_da import UNITS
from ..models import Ingredient, IngredientAlias, RecipeIngredient
from .deps import CurrentUser, DbSession
from .recipes import ingredient_ref
from .schemas import IngredientIn, IngredientOut, ParsedOut, ParseIn

router = APIRouter(prefix="/api")


@router.get("/meta")
def meta(_: CurrentUser) -> dict:
    return {
        "departments": [{"code": c, "name": n} for c, n in DEPARTMENTS.items()],
        "units": sorted({u for u in UNITS.values() if u}),
    }


@router.post("/parse")
def parse(body: ParseIn, session: DbSession, _: CurrentUser) -> list[ParsedOut]:
    """Læs ingredienslinjer uden at gemme dem (til redigering)."""
    catalog = Catalog(session)
    out = []
    for raw in body.lines:
        p = catalog.parse(raw)
        out.append(ParsedOut(
            raw=p.raw, quantity=p.quantity, quantity_max=p.quantity_max, unit=p.unit, item=p.item,
            note=p.note, ingredient=ingredient_ref(catalog.by_id.get(p.ingredient_id)),
            match_status=p.match_status,
        ))
    return out


def _out(ing: Ingredient, used: int) -> IngredientOut:
    return IngredientOut(
        id=ing.id, name=ing.name, department=ing.department, pantry=ing.pantry,
        grams_per_piece=ing.grams_per_piece, grams_per_dl=ing.grams_per_dl,
        aliases=sorted(a.alias for a in ing.aliases), used_in=used,
    )


@router.get("/ingredients")
def list_ingredients(session: DbSession, _: CurrentUser) -> list[IngredientOut]:
    used = dict(session.execute(
        select(RecipeIngredient.ingredient_id, func.count(func.distinct(RecipeIngredient.recipe_id)))
        .group_by(RecipeIngredient.ingredient_id)
    ).all())
    rows = session.scalars(select(Ingredient).options(selectinload(Ingredient.aliases)).order_by(Ingredient.name))
    return [_out(i, used.get(i.id, 0)) for i in rows]


def _validate(session, body: IngredientIn, own: Ingredient | None = None) -> None:
    if body.department not in DEPARTMENTS:
        raise HTTPException(status_code=422, detail="Ukendt afdeling")
    k = key(body.name)
    for other in session.scalars(select(Ingredient)):
        if other is not own and key(other.name) == k:
            raise HTTPException(status_code=409, detail=f"Varen {other.name!r} findes allerede")
    alias = session.scalar(select(IngredientAlias).where(IngredientAlias.key == k))
    if alias and alias.ingredient is not own:
        raise HTTPException(
            status_code=409, detail=f"{body.name!r} er allerede et andet navn for {alias.ingredient.name!r}"
        )


def _fill(ing: Ingredient, body: IngredientIn) -> None:
    ing.name = " ".join(body.name.lower().split())
    ing.department = body.department
    ing.pantry = body.pantry
    ing.grams_per_piece = body.grams_per_piece
    ing.grams_per_dl = body.grams_per_dl


@router.post("/ingredients", status_code=201)
def create_ingredient(body: IngredientIn, session: DbSession, _: CurrentUser) -> IngredientOut:
    _validate(session, body)
    ing = Ingredient()
    _fill(ing, body)
    session.add(ing)
    session.commit()
    return _out(ing, 0)


@router.put("/ingredients/{ingredient_id}")
def update_ingredient(ingredient_id: int, body: IngredientIn, session: DbSession, _: CurrentUser) -> IngredientOut:
    ing = session.get(Ingredient, ingredient_id)
    if ing is None:
        raise HTTPException(status_code=404, detail="Varen findes ikke")
    _validate(session, body, ing)
    old = ing.name
    _fill(ing, body)
    if key(old) != key(ing.name) and not any(a.key == key(old) for a in ing.aliases):
        # Det gamle navn bliver et alias, så opskrifter og startdata stadig finder varen.
        ing.aliases.append(IngredientAlias(alias=old, key=key(old), source="user"))
    session.commit()
    used = session.scalar(
        select(func.count(func.distinct(RecipeIngredient.recipe_id))).where(RecipeIngredient.ingredient_id == ing.id)
    )
    return _out(ing, used or 0)
