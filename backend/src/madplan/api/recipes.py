from urllib.parse import urlparse

import uuid

from fastapi import APIRouter, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from .. import importer, search_nemlig, search_valdemarsro
from ..adjustments import load_adjustments
from ..catalog import Catalog, learn_alias, suggest_main
from ..models import (
    Household,
    HouseholdRecipe,
    HouseholdRecipeAdjustment,
    HouseholdRecipeNote,
    Ingredient,
    Plan,
    PlanMeal,
    Recipe,
    RecipeIngredient,
    WishlistItem,
)
from .deps import AppSettings, CurrentHousehold, DbSession, pantry_ids
from .schemas import (
    ExtraLineOut,
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


def ingredient_ref(ing: Ingredient | None, pantry: set[int] | frozenset[int] = frozenset()) -> IngredientRef | None:
    """`pantry`: familiens basisvarer (pantry_ids)."""
    if ing is None:
        return None
    return IngredientRef(id=ing.id, name=ing.name, department=ing.department, pantry=ing.id in pantry)


def image_url(recipe: Recipe) -> str | None:
    return f"/api/images/{recipe.image_file}" if recipe.image_file else None


def recipe_out(recipe: Recipe, hh: Household, session: Session, warnings: list[str] | None = None) -> RecipeOut:
    """Opskriften set fra en familie: familiens egen note og basisvarer."""
    pantry = pantry_ids(session, hh.id)
    note = session.get(HouseholdRecipeNote, (hh.id, recipe.id))
    mine = session.get(HouseholdRecipe, (hh.id, recipe.id))
    adj = load_adjustments(session, hh.id, {recipe.id})[recipe.id]
    extras = []
    if adj.extras:
        catalog = Catalog(session)
        for a in adj.extras:
            p = catalog.parse(a.value)
            ing = catalog.by_id.get(p.ingredient_id) if p.match_status in ("sikker", "bekræftet") else None
            extras.append(ExtraLineOut(id=a.id, raw=a.value, quantity=p.quantity, unit=p.unit, item=p.item,
                                       ingredient=ingredient_ref(ing, pantry)))
    return RecipeOut(
        extra_lines=extras, own_note=adj.note,
        in_collection=mine is not None, favorite=bool(mine and mine.favorite),
        id=recipe.id,
        title=recipe.title,
        servings=recipe.servings,
        instructions=[s for s in recipe.instructions.split("\n") if s.strip()],
        child_note=note.child_note if note else "",
        owned=recipe.created_by_household == hh.id,
        source_url=recipe.source_url,
        image_url=image_url(recipe),
        ingredients=[
            LineOut(
                id=l.id, raw=l.raw, group=l.group, quantity=l.quantity, quantity_max=l.quantity_max,
                unit=l.unit, item=l.item, note=l.note, ingredient=ingredient_ref(l.ingredient, pantry),
                match_status=l.match_status, is_main=l.is_main,
                skipped=l.id in adj.skip, my_quantity=adj.quantity.get(l.id),
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


def load_own_recipe(session: Session, recipe_id: int, hh: Household) -> Recipe:
    """Opskriften, hvis familien ejer den. Kun ejerfamilien kan rette en fælles
    opskrift (flere-familier.md §4); alle andre får 404."""
    recipe = load_recipe(session, recipe_id)
    if recipe.created_by_household != hh.id:
        raise HTTPException(status_code=404, detail="Opskriften findes ikke")
    return recipe


def add_to_collection(session: Session, hh_id: int, recipe_id: int) -> None:
    """Læg opskriften i familiens samling (gør intet, hvis den allerede er der)."""
    if session.get(HouseholdRecipe, (hh_id, recipe_id)) is None:
        session.add(HouseholdRecipe(household_id=hh_id, recipe_id=recipe_id))


def _set_note(session: Session, hh: Household, recipe: Recipe, text: str) -> None:
    note = session.get(HouseholdRecipeNote, (hh.id, recipe.id))
    if note is None:
        session.add(HouseholdRecipeNote(household_id=hh.id, recipe_id=recipe.id, child_note=text))
    else:
        note.child_note = text


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
    recipe.source_url = (body.source_url or "").strip() or None


def _check_duplicate(session: Session, url: str | None, own_id: int | None = None, adopt: Household | None = None) -> None:
    if not url:
        return
    # Samme opskrift med og uden "/" til sidst er den samme.
    want = url.strip().rstrip("/").lower()
    other = next((r for r in session.scalars(select(Recipe).where(Recipe.source_url.is_not(None)))
                  if r.source_url.strip().rstrip("/").lower() == want), None)
    if other and other.id != own_id:
        if adopt is not None:
            # Samme ret importeres igen (fx af en anden familie): den genbruges og lægges i samlingen.
            add_to_collection(session, adopt.id, other.id)
            session.commit()
        raise HTTPException(status_code=409, detail={"message": "Opskriften findes allerede", "id": other.id})


@router.get("/recipes")
def list_recipes(session: DbSession, hh: CurrentHousehold, q: str = "", alle: bool = False) -> list[RecipeSummary]:
    """Familiens samling. Med `alle=true` alle fælles opskrifter (også dem, familien ikke bruger)."""
    mine = {r.recipe_id: r for r in session.scalars(select(HouseholdRecipe).where(HouseholdRecipe.household_id == hh.id))}
    stmt = select(Recipe).options(selectinload(Recipe.ingredients).selectinload(RecipeIngredient.ingredient))
    # Søgning i Python: SQLites LIKE kender kun store/små bogstaver for ASCII (æ/Æ),
    # og % og _ ville være jokertegn.
    needle = q.strip().casefold()
    out = []
    for r in session.scalars(stmt.order_by(func.lower(Recipe.title))):
        if needle and needle not in r.title.casefold():
            continue
        if not alle and r.id not in mine:
            continue
        out.append(RecipeSummary(
            id=r.id,
            title=r.title,
            servings=r.servings,
            image_url=image_url(r),
            source_host=urlparse(r.source_url).hostname.removeprefix("www.") if r.source_url else None,
            main_ingredients=[l.ingredient.name for l in r.ingredients if l.is_main and l.ingredient],
            ingredients=sorted({l.ingredient.name if l.ingredient else l.item for l in r.ingredients}),
            # Kun ejerfamilien kan rette linjerne, så kun den ser dem som "til tjek".
            to_review=sum(1 for l in r.ingredients if l.match_status in NEEDS_REVIEW) if r.created_by_household == hh.id else 0,
            owned=r.created_by_household == hh.id,
            in_collection=r.id in mine, favorite=bool(r.id in mine and mine[r.id].favorite),
        ))
    return out


@router.post("/recipes", status_code=201)
def create_recipe(body: RecipeIn, session: DbSession, hh: CurrentHousehold) -> RecipeOut:
    _check_duplicate(session, body.source_url)
    recipe = Recipe(created_by_household=hh.id)
    _fill_recipe(recipe, body)
    session.add(recipe)
    session.flush()
    _set_note(session, hh, recipe, body.child_note.strip())
    add_to_collection(session, hh.id, recipe.id)
    catalog = Catalog(session)
    apply_lines(session, recipe, body.ingredients, catalog)
    if not any(l.is_main for l in recipe.ingredients):
        suggest_main(recipe.ingredients, catalog.by_id)
    session.commit()
    return recipe_out(load_recipe(session, recipe.id), hh, session)


@router.post("/recipes/import", status_code=201)
def import_recipe(body: ImportIn, session: DbSession, settings: AppSettings, hh: CurrentHousehold) -> RecipeOut:
    url = body.url.strip()
    _check_duplicate(session, url, adopt=hh)
    session.commit()  # slip forbindelsen, mens vi venter på den andens side
    try:
        importer.check_url(url)
        scraped = importer.load(url)
    except importer.RecipeImportError as e:
        raise HTTPException(status_code=422, detail=str(e)) from None

    recipe = Recipe(
        title=scraped.title[:200],
        servings=scraped.servings if scraped.servings and scraped.servings <= 100 else None,
        instructions=_clean_steps(scraped.instructions),
        source_url=url,
        created_by_household=hh.id,
    )
    warnings = list(scraped.warnings)
    if scraped.image_url:
        recipe.image_file = importer.download_image(scraped.image_url, settings.image_dir)
        if not recipe.image_file:
            warnings.append("Billedet kunne ikke hentes")
    session.add(recipe)
    session.flush()
    add_to_collection(session, hh.id, recipe.id)
    catalog = Catalog(session)
    lines = [LineIn(raw=raw[:300], group=g.name[:100]) for g in scraped.groups for raw in g.lines]
    apply_lines(session, recipe, lines, catalog)
    suggest_main(recipe.ingredients, catalog.by_id)
    session.commit()
    return recipe_out(load_recipe(session, recipe.id), hh, session, warnings)


@router.get("/recipes/{recipe_id}")
def get_recipe(recipe_id: int, session: DbSession, hh: CurrentHousehold) -> RecipeOut:
    return recipe_out(load_recipe(session, recipe_id), hh, session)


@router.put("/recipes/{recipe_id}")
def update_recipe(recipe_id: int, body: RecipeIn, session: DbSession, hh: CurrentHousehold) -> RecipeOut:
    recipe = load_own_recipe(session, recipe_id, hh)
    _check_duplicate(session, body.source_url, recipe.id)
    _fill_recipe(recipe, body)
    _set_note(session, hh, recipe, body.child_note.strip())
    apply_lines(session, recipe, body.ingredients, Catalog(session))
    session.commit()
    session.expire_all()
    return recipe_out(load_recipe(session, recipe.id), hh, session)


# Billeder, man selv tager eller vælger. Telefonen gør dem mindre før upload,
# men serveren tjekker alligevel størrelse og filtype (ud fra indholdet).
MAX_UPLOAD = 8_000_000
_IMAGE_MAGIC = [(b"\xff\xd8\xff", ".jpg"), (b"\x89PNG\r\n\x1a\n", ".png")]


def _image_ext(head: bytes) -> str | None:
    for magic, ext in _IMAGE_MAGIC:
        if head.startswith(magic):
            return ext
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return ".webp"
    return None


@router.post("/recipes/{recipe_id}/image")
async def upload_image(recipe_id: int, file: UploadFile, session: DbSession, settings: AppSettings, hh: CurrentHousehold) -> RecipeOut:
    """Sæt eller skift opskriftens billede (JPEG, PNG eller WebP)."""
    recipe = load_own_recipe(session, recipe_id, hh)
    data = await file.read(MAX_UPLOAD + 1)
    if len(data) > MAX_UPLOAD:
        raise HTTPException(status_code=413, detail="Billedet er for stort (højst 8 MB)")
    ext = _image_ext(data[:16])
    if ext is None:
        raise HTTPException(status_code=422, detail="Filen er ikke et billede (JPEG, PNG eller WebP)")
    settings.image_dir.mkdir(parents=True, exist_ok=True)
    name = uuid.uuid4().hex + ext
    (settings.image_dir / name).write_bytes(data)
    old = recipe.image_file
    recipe.image_file = name
    session.commit()
    if old:
        (settings.image_dir / old).unlink(missing_ok=True)
    return recipe_out(load_recipe(session, recipe.id), hh, session)


@router.delete("/recipes/{recipe_id}/image")
def delete_image(recipe_id: int, session: DbSession, settings: AppSettings, hh: CurrentHousehold) -> RecipeOut:
    recipe = load_own_recipe(session, recipe_id, hh)
    old = recipe.image_file
    recipe.image_file = None
    session.commit()
    if old:
        (settings.image_dir / old).unlink(missing_ok=True)
    return recipe_out(load_recipe(session, recipe.id), hh, session)


@router.post("/recipes/{recipe_id}/collection")
def put_in_collection(recipe_id: int, session: DbSession, hh: CurrentHousehold) -> RecipeOut:
    """Læg en fælles opskrift i familiens samling."""
    recipe = load_recipe(session, recipe_id)
    add_to_collection(session, hh.id, recipe.id)
    session.commit()
    return recipe_out(recipe, hh, session)


@router.delete("/recipes/{recipe_id}/collection")
def take_out_of_collection(recipe_id: int, session: DbSession, hh: CurrentHousehold) -> RecipeOut:
    """Fjern opskriften fra familiens samling (den slettes ikke). Planer, der bruger den, røres ikke."""
    recipe = load_recipe(session, recipe_id)
    row = session.get(HouseholdRecipe, (hh.id, recipe.id))
    if row is not None:
        session.delete(row)
        session.commit()
    return recipe_out(recipe, hh, session)


class FavoriteIn(BaseModel):
    favorite: bool


@router.put("/recipes/{recipe_id}/favorite")
def set_favorite(recipe_id: int, body: FavoriteIn, session: DbSession, hh: CurrentHousehold) -> RecipeOut:
    recipe = load_recipe(session, recipe_id)
    add_to_collection(session, hh.id, recipe.id)
    session.flush()
    session.get(HouseholdRecipe, (hh.id, recipe.id)).favorite = body.favorite
    session.commit()
    return recipe_out(recipe, hh, session)


class NoteIn(BaseModel):
    child_note: str = Field("", max_length=2000)


@router.put("/recipes/{recipe_id}/note")
def put_note(recipe_id: int, body: NoteIn, session: DbSession, hh: CurrentHousehold) -> RecipeOut:
    """Familiens egen note om barnet på en fælles opskrift (rører ikke opskriften)."""
    recipe = load_recipe(session, recipe_id)
    _set_note(session, hh, recipe, body.child_note.strip())
    session.commit()
    return recipe_out(recipe, hh, session)


# --- Familiens tilpasninger (lagt oven på den fælles opskrift) --------------------------------


class LineAdjustIn(BaseModel):
    skip: bool = False
    # Egen mængde (samme enhed som linjen). null = den fælles mængde.
    quantity: float | None = Field(None, ge=0, le=100_000)


@router.put("/recipes/{recipe_id}/adjustments/lines/{line_id}")
def adjust_line(recipe_id: int, line_id: int, body: LineAdjustIn, session: DbSession, hh: CurrentHousehold) -> RecipeOut:
    """Spring en linje over og/eller brug en egen mængde. Gælder kun denne familie."""
    recipe = load_recipe(session, recipe_id)
    if line_id not in {l.id for l in recipe.ingredients}:
        raise HTTPException(status_code=404, detail="Linjen findes ikke")
    for a in session.scalars(select(HouseholdRecipeAdjustment).where(
            HouseholdRecipeAdjustment.household_id == hh.id, HouseholdRecipeAdjustment.line_id == line_id)):
        session.delete(a)
    session.flush()
    if body.skip:
        session.add(HouseholdRecipeAdjustment(household_id=hh.id, recipe_id=recipe.id, line_id=line_id, type="skip"))
    elif body.quantity is not None:
        session.add(HouseholdRecipeAdjustment(household_id=hh.id, recipe_id=recipe.id, line_id=line_id,
                                              type="quantity", quantity=body.quantity))
    add_to_collection(session, hh.id, recipe.id)
    session.commit()
    return recipe_out(recipe, hh, session)


class ExtraLineIn(BaseModel):
    raw: str = Field(min_length=1, max_length=300)


@router.post("/recipes/{recipe_id}/adjustments/extra", status_code=201)
def add_extra_line(recipe_id: int, body: ExtraLineIn, session: DbSession, hh: CurrentHousehold) -> RecipeOut:
    """Ekstra linje til familiens udgave ("1 dåse majs")."""
    recipe = load_recipe(session, recipe_id)
    raw = " ".join(body.raw.split())
    if not raw:
        raise HTTPException(status_code=422, detail="Skriv en linje")
    n = session.scalar(select(func.count()).select_from(HouseholdRecipeAdjustment).where(
        HouseholdRecipeAdjustment.household_id == hh.id, HouseholdRecipeAdjustment.recipe_id == recipe.id,
        HouseholdRecipeAdjustment.type == "extra")) or 0
    if n >= 30:
        raise HTTPException(status_code=422, detail="For mange ekstra linjer")
    session.add(HouseholdRecipeAdjustment(household_id=hh.id, recipe_id=recipe.id, type="extra", value=raw))
    add_to_collection(session, hh.id, recipe.id)
    session.commit()
    return recipe_out(recipe, hh, session)


class OwnNoteIn(BaseModel):
    text: str = Field("", max_length=2000)


@router.put("/recipes/{recipe_id}/adjustments/note")
def put_own_note(recipe_id: int, body: OwnNoteIn, session: DbSession, hh: CurrentHousehold) -> RecipeOut:
    """Familiens egen note på opskriften ("Vi bruger halv chili"). Noten om barnet er en anden."""
    recipe = load_recipe(session, recipe_id)
    row = session.scalar(select(HouseholdRecipeAdjustment).where(
        HouseholdRecipeAdjustment.household_id == hh.id, HouseholdRecipeAdjustment.recipe_id == recipe.id,
        HouseholdRecipeAdjustment.type == "note"))
    text = body.text.strip()
    if row is not None and not text:
        session.delete(row)
    elif row is not None:
        row.value = text
    elif text:
        session.add(HouseholdRecipeAdjustment(household_id=hh.id, recipe_id=recipe.id, type="note", value=text))
    session.commit()
    return recipe_out(recipe, hh, session)


@router.delete("/recipes/{recipe_id}/adjustments/{adjustment_id}")
def remove_adjustment(recipe_id: int, adjustment_id: int, session: DbSession, hh: CurrentHousehold) -> RecipeOut:
    """Fjern en tilpasning (ekstra linje) igen. Andre familiers tilpasninger findes ikke."""
    recipe = load_recipe(session, recipe_id)
    row = session.scalar(select(HouseholdRecipeAdjustment).where(
        HouseholdRecipeAdjustment.id == adjustment_id, HouseholdRecipeAdjustment.household_id == hh.id,
        HouseholdRecipeAdjustment.recipe_id == recipe.id))
    if row is None:
        raise HTTPException(status_code=404, detail="Tilpasningen findes ikke")
    session.delete(row)
    session.commit()
    return recipe_out(recipe, hh, session)


@router.post("/recipes/{recipe_id}/suggest-main")
def suggest_main_route(recipe_id: int, session: DbSession, hh: CurrentHousehold) -> RecipeOut:
    recipe = load_own_recipe(session, recipe_id, hh)
    suggest_main(recipe.ingredients, Catalog(session).by_id)
    session.commit()
    return recipe_out(load_recipe(session, recipe.id), hh, session)


@router.delete("/recipes/{recipe_id}", status_code=204)
def delete_recipe(recipe_id: int, session: DbSession, settings: AppSettings, hh: CurrentHousehold) -> None:
    recipe = load_own_recipe(session, recipe_id, hh)
    # En opskrift, en anden familie bruger i sin plan, kan ikke slettes.
    in_use = session.scalar(
        select(func.count()).select_from(PlanMeal).join(Plan).where(
            PlanMeal.recipe_id == recipe.id, Plan.household_id != hh.id)
    ) or session.scalar(
        select(func.count()).select_from(WishlistItem).join(Plan).where(
            WishlistItem.recipe_id == recipe.id, Plan.household_id != hh.id)
    )
    in_collection = session.scalar(
        select(func.count()).select_from(HouseholdRecipe).where(
            HouseholdRecipe.recipe_id == recipe.id, HouseholdRecipe.household_id != hh.id)
    )
    if in_use or in_collection:
        raise HTTPException(status_code=409, detail="Opskriften bruges af en anden familie og kan ikke slettes")
    image = recipe.image_file
    session.delete(recipe)
    session.commit()
    if image:
        (settings.image_dir / image).unlink(missing_ok=True)


# --- Søgning på Valdemarsro og nemlig.com ------------------------------------

class ExternalHit(BaseModel):
    title: str
    url: str
    image_url: str
    # Opskriften er allerede importeret (id på vores egen opskrift)
    recipe_id: int | None = None


def _norm_url(url: str) -> str:
    return url.strip().rstrip("/").lower()


def _external_hits(session: Session, q: str, search) -> list[ExternalHit]:
    """Søg på en opskriftsside. Resultater, vi allerede har, markeres med recipe_id."""
    if len(q.strip()) < 3:
        return []
    session.commit()  # slip forbindelsen, mens vi venter på søgningen
    try:
        hits = search(q)
    except search_valdemarsro.SearchError as e:
        raise HTTPException(status_code=502, detail=str(e)) from None
    have = {_norm_url(u): i for i, u in session.execute(select(Recipe.id, Recipe.source_url).where(Recipe.source_url.is_not(None)))}
    return [ExternalHit(title=h.title, url=h.url, image_url=h.image_url, recipe_id=have.get(_norm_url(h.url))) for h in hits]


@router.get("/search/valdemarsro")
def search_valdemarsro_route(session: DbSession, _: CurrentHousehold, q: str = "") -> list[ExternalHit]:
    return _external_hits(session, q, search_valdemarsro.search)


@router.get("/search/nemlig")
def search_nemlig_route(session: DbSession, _: CurrentHousehold, q: str = "") -> list[ExternalHit]:
    """Kun nemlig.coms opskrifter, ikke deres varer."""
    return _external_hits(session, q, search_nemlig.search)


# --- Tjek af ingredienser på tværs af opskrifter -----------------------------

def _own_line(session: Session, line_id: int, hh: Household) -> RecipeIngredient | None:
    """Linjen, hvis den står i en opskrift, familien ejer; ellers None (-> 404)."""
    return session.scalar(
        select(RecipeIngredient).join(Recipe)
        .where(RecipeIngredient.id == line_id, Recipe.created_by_household == hh.id)
    )


@router.get("/review")
def review(session: DbSession, hh: CurrentHousehold) -> list[ReviewLine]:
    """Linjer, hvor varen er usikker eller mangler (kun i familiens egne opskrifter)."""
    pantry = pantry_ids(session, hh.id)
    rows = session.execute(
        select(RecipeIngredient, Recipe.title)
        .join(Recipe)
        .where(RecipeIngredient.match_status.in_(NEEDS_REVIEW), Recipe.created_by_household == hh.id)
        .options(selectinload(RecipeIngredient.ingredient))
        .order_by(RecipeIngredient.item, Recipe.title)
    )
    return [
        ReviewLine(
            id=l.id, recipe_id=l.recipe_id, recipe_title=title, raw=l.raw, item=l.item, unit=l.unit,
            ingredient=ingredient_ref(l.ingredient, pantry), match_status=l.match_status,
        )
        for l, title in rows
    ]


@router.post("/lines/{line_id}/confirm")
def confirm_line(line_id: int, body: LineConfirmIn, session: DbSession, hh: CurrentHousehold) -> dict:
    """Bekræft varen for en linje. Samme varenavn i andre opskrifter rettes også."""
    line = _own_line(session, line_id, hh)
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
def set_main(line_id: int, body: MainIn, session: DbSession, hh: CurrentHousehold) -> dict:
    """Sæt eller fjern stjernen (hovedingrediens) på en linje. Der må være flere."""
    line = _own_line(session, line_id, hh)
    if line is None:
        raise HTTPException(status_code=404, detail="Linjen findes ikke")
    line.is_main = body.is_main
    session.commit()
    return {"is_main": line.is_main}


@router.post("/lines/{line_id}/ignore")
def ignore_line(line_id: int, session: DbSession, hh: CurrentHousehold) -> dict:
    """Linjen skal ikke kobles til en vare (fx "vand" eller en pyntebemærkning)."""
    line = _own_line(session, line_id, hh)
    if line is None:
        raise HTTPException(status_code=404, detail="Linjen findes ikke")
    line.ingredient_id = None
    line.match_status = "bekræftet"
    session.commit()
    return {"also_updated": 0}
