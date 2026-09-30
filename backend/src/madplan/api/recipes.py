from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from .. import importer
from ..catalog import Catalog, learn_alias, suggest_main
from ..models import Ingredient, Recipe, RecipeIngredient
from .deps import AppSettings, CurrentUser, DbSession
from .schemas import (
    ImportIn,
    IngredientRef,
    LineConfirmIn,
    LineIn,
    LineOut,
    RecipeIn,
    RecipeOut,
    RecipeSummary,
    ReviewLine,
)

router = APIRouter(prefix="/api")
NEEDS_REVIEW = ("usikker", "ingen")


def ingredient_ref(ing: Ingredient | None) -> IngredientRef | None:
    if ing is None:
        return None
    return IngredientRef(id=ing.id, name=ing.name, department=ing.department, pantry=ing.pantry)


def image_url(recipe: Recipe) -> str | None:
    return f"/api/images/{recipe.image_file}" if recipe.image_file else None


def recipe_out(recipe: Recipe, warnings: list[str] | None = None) -> RecipeOut:
    return RecipeOut(
        id=recipe.id,
        title=recipe.title,
        servings=recipe.servings,
        instructions=[s for s in recipe.instructions.split("\n") if s.strip()],
        child_note=recipe.child_note,
        source_url=recipe.source_url,
        image_url=image_url(recipe),
        ingredients=[
            LineOut(
                id=l.id, raw=l.raw, group=l.group, quantity=l.quantity, quantity_max=l.quantity_max,
                unit=l.unit, item=l.item, note=l.note, ingredient=ingredient_ref(l.ingredient),
                match_status=l.match_status, is_main=l.is_main,
            )
            for l in recipe.ingredients
        ],
        warnings=warnings or [],
    )


def load_recipe(session: Session, recipe_id: int) -> Recipe:
    recipe = session.scalar(
        select(Recipe)
        .where(Recipe.id == recipe_id)
        .options(selectinload(Recipe.ingredients).selectinload(RecipeIngredient.ingredient))
    )
    if recipe is None:
        raise HTTPException(status_code=404, detail="Opskriften findes ikke")
    return recipe


def _clean_steps(steps: list[str]) -> str:
    return "\n".join(" ".join(s.split()) for s in steps if s.strip())


def apply_lines(session: Session, recipe: Recipe, lines: list[LineIn], catalog: Catalog) -> None:
    """Opdatér opskriftens linjer. Linjer med id beholdes (planen peger på dem),
    nye oprettes, og linjer, der ikke er med, slettes."""
    existing = {l.id: l for l in recipe.ingredients}
    keep: list[RecipeIngredient] = []
    confirmed: list[RecipeIngredient] = []
    for pos, li in enumerate(lines):
        if not li.raw.strip():
            continue
        if li.id is not None and li.id not in existing:
            raise HTTPException(status_code=422, detail=f"Linje {li.id} hører ikke til opskriften")
        line = existing.get(li.id) if li.id is not None else None
        before = (line.ingredient_id, line.match_status) if line is not None else (None, None)
        if line is None:
            line = RecipeIngredient()
            recipe.ingredients.append(line)
        line.position = pos
        line.group = li.group.strip()
        line.raw = li.raw.strip()
        line.is_main = li.is_main
        if li.item is None:
            p = catalog.parse(li.raw)
            line.quantity, line.quantity_max, line.unit = p.quantity, p.quantity_max, p.unit
            line.item, line.note = p.item, p.note
            line.ingredient_id, line.match_status = p.ingredient_id, p.match_status
        else:
            if li.ingredient_id is not None and li.ingredient_id not in catalog.by_id:
                raise HTTPException(status_code=422, detail="Ukendt vare")
            line.quantity, line.quantity_max, line.unit = li.quantity, li.quantity_max, li.unit or None
            line.item, line.note = li.item.strip(), (li.note or "").strip() or None
            line.ingredient_id = li.ingredient_id
            # "bekræftet" uden vare betyder, at linjen bevidst ikke er koblet.
            line.match_status = li.match_status if li.ingredient_id or li.match_status == "bekræftet" else "ingen"
            # Lær kun af NYE bekræftelser. Ellers ville hver gemning genlære alle
            # opskriftens gamle valg og rette andre opskrifter frem og tilbage.
            if line.match_status == "bekræftet" and line.ingredient_id and before != (line.ingredient_id, "bekræftet"):
                confirmed.append(line)
        keep.append(line)
    recipe.ingredients[:] = keep
    session.flush()
    for line in confirmed:
        learn_alias(session, line.item, catalog.by_id[line.ingredient_id])


def _fill_recipe(recipe: Recipe, body: RecipeIn) -> None:
    recipe.title = body.title.strip()
    recipe.servings = body.servings
    recipe.instructions = _clean_steps(body.instructions)
    recipe.child_note = body.child_note.strip()
    recipe.source_url = (body.source_url or "").strip() or None


def _check_duplicate(session: Session, url: str | None, own_id: int | None = None) -> None:
    if not url:
        return
    other = session.scalar(select(Recipe).where(Recipe.source_url == url))
    if other and other.id != own_id:
        raise HTTPException(status_code=409, detail={"message": "Opskriften findes allerede", "id": other.id})


@router.get("/recipes")
def list_recipes(session: DbSession, _: CurrentUser, q: str = "") -> list[RecipeSummary]:
    stmt = select(Recipe).options(selectinload(Recipe.ingredients).selectinload(RecipeIngredient.ingredient))
    if q.strip():
        stmt = stmt.where(Recipe.title.icontains(q.strip()))
    out = []
    for r in session.scalars(stmt.order_by(func.lower(Recipe.title))):
        out.append(RecipeSummary(
            id=r.id,
            title=r.title,
            servings=r.servings,
            image_url=image_url(r),
            source_host=urlparse(r.source_url).hostname.removeprefix("www.") if r.source_url else None,
            main_ingredients=[l.ingredient.name for l in r.ingredients if l.is_main and l.ingredient],
            to_review=sum(1 for l in r.ingredients if l.match_status in NEEDS_REVIEW),
        ))
    return out


@router.post("/recipes", status_code=201)
def create_recipe(body: RecipeIn, session: DbSession, _: CurrentUser) -> RecipeOut:
    _check_duplicate(session, body.source_url)
    recipe = Recipe()
    _fill_recipe(recipe, body)
    session.add(recipe)
    catalog = Catalog(session)
    apply_lines(session, recipe, body.ingredients, catalog)
    if not any(l.is_main for l in recipe.ingredients):
        suggest_main(recipe.ingredients, catalog.by_id)
    session.commit()
    return recipe_out(load_recipe(session, recipe.id))


@router.post("/recipes/import", status_code=201)
def import_recipe(body: ImportIn, session: DbSession, settings: AppSettings, _: CurrentUser) -> RecipeOut:
    url = body.url.strip()
    _check_duplicate(session, url)
    try:
        importer.check_url(url)
        scraped = importer.scrape(importer.fetch(url), url)
    except importer.RecipeImportError as e:
        raise HTTPException(status_code=422, detail=str(e)) from None

    recipe = Recipe(
        title=scraped.title[:200],
        servings=scraped.servings if scraped.servings and scraped.servings <= 100 else None,
        instructions=_clean_steps(scraped.instructions),
        child_note="",
        source_url=url,
    )
    warnings = list(scraped.warnings)
    if scraped.image_url:
        recipe.image_file = importer.download_image(scraped.image_url, settings.image_dir)
        if not recipe.image_file:
            warnings.append("Billedet kunne ikke hentes")
    session.add(recipe)
    catalog = Catalog(session)
    lines = [LineIn(raw=raw[:300], group=g.name[:100]) for g in scraped.groups for raw in g.lines]
    apply_lines(session, recipe, lines, catalog)
    suggest_main(recipe.ingredients, catalog.by_id)
    session.commit()
    return recipe_out(load_recipe(session, recipe.id), warnings)


@router.get("/recipes/{recipe_id}")
def get_recipe(recipe_id: int, session: DbSession, _: CurrentUser) -> RecipeOut:
    return recipe_out(load_recipe(session, recipe_id))


@router.put("/recipes/{recipe_id}")
def update_recipe(recipe_id: int, body: RecipeIn, session: DbSession, _: CurrentUser) -> RecipeOut:
    recipe = load_recipe(session, recipe_id)
    _check_duplicate(session, body.source_url, recipe.id)
    _fill_recipe(recipe, body)
    apply_lines(session, recipe, body.ingredients, Catalog(session))
    session.commit()
    session.expire_all()
    return recipe_out(load_recipe(session, recipe.id))


@router.post("/recipes/{recipe_id}/suggest-main")
def suggest_main_route(recipe_id: int, session: DbSession, _: CurrentUser) -> RecipeOut:
    recipe = load_recipe(session, recipe_id)
    suggest_main(recipe.ingredients, Catalog(session).by_id)
    session.commit()
    return recipe_out(load_recipe(session, recipe.id))


@router.delete("/recipes/{recipe_id}", status_code=204)
def delete_recipe(recipe_id: int, session: DbSession, settings: AppSettings, _: CurrentUser) -> None:
    recipe = load_recipe(session, recipe_id)
    image = recipe.image_file
    session.delete(recipe)
    session.commit()
    if image:
        (settings.image_dir / image).unlink(missing_ok=True)


# --- Tjek af ingredienser på tværs af opskrifter -----------------------------

@router.get("/review")
def review(session: DbSession, _: CurrentUser) -> list[ReviewLine]:
    """Linjer, hvor varen er usikker eller mangler."""
    rows = session.execute(
        select(RecipeIngredient, Recipe.title)
        .join(Recipe)
        .where(RecipeIngredient.match_status.in_(NEEDS_REVIEW))
        .options(selectinload(RecipeIngredient.ingredient))
        .order_by(RecipeIngredient.item, Recipe.title)
    )
    return [
        ReviewLine(
            id=l.id, recipe_id=l.recipe_id, recipe_title=title, raw=l.raw, item=l.item, unit=l.unit,
            ingredient=ingredient_ref(l.ingredient), match_status=l.match_status,
        )
        for l, title in rows
    ]


@router.post("/lines/{line_id}/confirm")
def confirm_line(line_id: int, body: LineConfirmIn, session: DbSession, _: CurrentUser) -> dict:
    """Bekræft varen for en linje. Samme varenavn i andre opskrifter rettes også."""
    line = session.get(RecipeIngredient, line_id)
    ing = session.get(Ingredient, body.ingredient_id)
    if line is None or ing is None:
        raise HTTPException(status_code=404, detail="Linje eller vare findes ikke")
    line.ingredient_id = ing.id
    line.match_status = "bekræftet"
    session.flush()
    also = learn_alias(session, line.item, ing)
    session.commit()
    return {"also_updated": also}


class MainIn(BaseModel):
    is_main: bool


@router.put("/lines/{line_id}/main")
def set_main(line_id: int, body: MainIn, session: DbSession, _: CurrentUser) -> dict:
    """Sæt eller fjern stjernen (hovedingrediens) på en linje. Der må være flere."""
    line = session.get(RecipeIngredient, line_id)
    if line is None:
        raise HTTPException(status_code=404, detail="Linjen findes ikke")
    line.is_main = body.is_main
    session.commit()
    return {"is_main": line.is_main}


@router.post("/lines/{line_id}/ignore")
def ignore_line(line_id: int, session: DbSession, _: CurrentUser) -> dict:
    """Linjen skal ikke kobles til en vare (fx "vand" eller en pyntebemærkning)."""
    line = session.get(RecipeIngredient, line_id)
    if line is None:
        raise HTTPException(status_code=404, detail="Linjen findes ikke")
    line.ingredient_id = None
    line.match_status = "bekræftet"
    session.commit()
    return {"also_updated": 0}
