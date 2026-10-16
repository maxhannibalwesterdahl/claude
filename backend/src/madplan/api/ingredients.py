from fastapi import APIRouter, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from ..catalog import Catalog, rematch_open_lines
from ..ingredients.matcher import DEPARTMENTS, key
from ..ingredients.parser_da import UNITS
from ..models import HouseholdPantry, Ingredient, IngredientAlias, RecipeIngredient
from .deps import CurrentHousehold, CurrentUser, DbSession, pantry_ids
from .recipes import ingredient_ref
from .schemas import IngredientIn, IngredientOut, ParsedOut, ParseIn

router = APIRouter(prefix="/api")


@router.get("/meta")
def meta(_: CurrentHousehold) -> dict:
    return {
        "departments": [{"code": c, "name": n} for c, n in DEPARTMENTS.items()],
        "units": sorted({u for u in UNITS.values() if u}),
    }


@router.post("/parse")
def parse(body: ParseIn, session: DbSession, hh: CurrentHousehold) -> list[ParsedOut]:
    """Læs ingredienslinjer uden at gemme dem (til redigering)."""
    catalog = Catalog(session)
    pantry = pantry_ids(session, hh.id)
    out = []
    for raw in body.lines:
        p = catalog.parse(raw)
        out.append(ParsedOut(
            raw=p.raw, quantity=p.quantity, quantity_max=p.quantity_max, unit=p.unit, item=p.item,
            note=p.note, ingredient=ingredient_ref(catalog.by_id.get(p.ingredient_id), pantry),
            match_status=p.match_status,
        ))
    return out


def _out(ing: Ingredient, used: int, pantry: set[int]) -> IngredientOut:
    return IngredientOut(
        id=ing.id, name=ing.name, department=ing.department, pantry=ing.id in pantry,
        grams_per_piece=ing.grams_per_piece, grams_per_dl=ing.grams_per_dl,
        aliases=sorted(a.alias for a in ing.aliases), used_in=used,
    )


@router.get("/ingredients")
def list_ingredients(session: DbSession, hh: CurrentHousehold) -> list[IngredientOut]:
    used = dict(session.execute(
        select(RecipeIngredient.ingredient_id, func.count(func.distinct(RecipeIngredient.recipe_id)))
        .group_by(RecipeIngredient.ingredient_id)
    ).all())
    rows = session.scalars(select(Ingredient).options(selectinload(Ingredient.aliases)).order_by(Ingredient.name))
    pantry = pantry_ids(session, hh.id)
    return [_out(i, used.get(i.id, 0), pantry) for i in rows]


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


def _set_pantry(session, hh_id: int, ing: Ingredient, pantry: bool) -> None:
    """Basisvare er familiens eget valg (household_pantry), ikke en egenskab ved varen."""
    row = session.get(HouseholdPantry, (hh_id, ing.id))
    if pantry and row is None:
        session.add(HouseholdPantry(household_id=hh_id, ingredient_id=ing.id))
    elif not pantry and row is not None:
        session.delete(row)


def _fill(ing: Ingredient, body: IngredientIn) -> None:
    ing.name = " ".join(body.name.lower().split())
    ing.department = body.department
    ing.grams_per_piece = body.grams_per_piece
    ing.grams_per_dl = body.grams_per_dl


@router.post("/ingredients", status_code=201)
def create_ingredient(body: IngredientIn, session: DbSession, hh: CurrentHousehold) -> IngredientOut:
    _validate(session, body)
    ing = Ingredient()
    _fill(ing, body)
    session.add(ing)
    session.flush()
    _set_pantry(session, hh.id, ing, body.pantry)
    # Andre opskrifter med samme varenavn får den nye vare med det samme.
    rematch_open_lines(session)
    session.commit()
    return _out(ing, 0, pantry_ids(session, hh.id))


def update_catalog(session, ing: Ingredient, body: IngredientIn) -> None:
    """Ret den fælles vare (navn, afdeling, omregning). Kun systemadmin."""
    _validate(session, body, ing)
    old = ing.name
    _fill(ing, body)
    if key(old) != key(ing.name) and not any(a.key == key(old) for a in ing.aliases):
        # Det gamle navn bliver et alias, så opskrifter og startdata stadig finder varen.
        ing.aliases.append(IngredientAlias(alias=old, key=key(old), source="user"))


def _catalog_fields_changed(ing: Ingredient, body: IngredientIn) -> bool:
    return (
        " ".join(body.name.lower().split()) != ing.name
        or body.department != ing.department
        or body.grams_per_piece != ing.grams_per_piece
        or body.grams_per_dl != ing.grams_per_dl
    )


@router.put("/ingredients/{ingredient_id}")
def update_ingredient(ingredient_id: int, body: IngredientIn, session: DbSession, hh: CurrentHousehold,
                      user: CurrentUser) -> IngredientOut:
    """Familien kan sætte sin egen basisvare. Varens navn, afdeling og omregning er
    fælles for alle familier og rettes kun af systemadmin (flere-familier.md §3)."""
    ing = session.get(Ingredient, ingredient_id)
    if ing is None:
        raise HTTPException(status_code=404, detail="Varen findes ikke")
    if _catalog_fields_changed(ing, body):
        if not user.is_system_admin:
            raise HTTPException(status_code=403, detail="Varekataloget er fælles. Kun administratoren kan rette en vare")
        update_catalog(session, ing, body)
    _set_pantry(session, hh.id, ing, body.pantry)
    session.commit()
    used = session.scalar(
        select(func.count(func.distinct(RecipeIngredient.recipe_id))).where(RecipeIngredient.ingredient_id == ing.id)
    )
    return _out(ing, used or 0, pantry_ids(session, hh.id))
