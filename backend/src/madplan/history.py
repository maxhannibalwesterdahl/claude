"""Historik og fortryd: opskriftsversioner (ejerfamilien) og kataloghistorik (systemadmin)."""

import json

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .models import (
    CatalogChange,
    Ingredient,
    IngredientAlias,
    Recipe,
    RecipeIngredient,
    RecipeVersion,
)

KEEP_VERSIONS = 30
LINE_FIELDS = ("position", "group", "raw", "quantity", "quantity_max", "unit", "item", "note",
               "ingredient_id", "match_status", "is_main")


def snapshot(recipe: Recipe) -> str:
    return json.dumps({
        "title": recipe.title, "servings": recipe.servings, "instructions": recipe.instructions,
        "source_url": recipe.source_url, "image_file": recipe.image_file,
        "lines": [{"id": l.id, **{f: getattr(l, f) for f in LINE_FIELDS}} for l in recipe.ingredients],
    }, ensure_ascii=False)


def save_version(session: Session, recipe: Recipe, household_id: int | None, user_id: int | None) -> None:
    """Gem den nuværende udgave, før den ændres. Kun de nyeste gemmes."""
    session.add(RecipeVersion(recipe_id=recipe.id, household_id=household_id, user_id=user_id, data=snapshot(recipe)))
    session.flush()
    old = session.scalars(select(RecipeVersion.id).where(RecipeVersion.recipe_id == recipe.id)
                          .order_by(RecipeVersion.id.desc()).offset(KEEP_VERSIONS)).all()
    if old:
        session.execute(delete(RecipeVersion).where(RecipeVersion.id.in_(old)))


def restore_version(session: Session, recipe: Recipe, version: RecipeVersion) -> None:
    """Sæt opskriften tilbage til en gammel udgave. Linjer, der stadig findes, beholder deres id
    (planer og "har hjemme" peger på dem); slettede linjer oprettes igen med nyt id."""
    data = json.loads(version.data)
    recipe.title, recipe.servings = data["title"], data["servings"]
    recipe.instructions, recipe.source_url = data["instructions"], data["source_url"]
    existing = {l.id: l for l in recipe.ingredients}
    known = set(session.scalars(select(Ingredient.id)))
    keep: list[RecipeIngredient] = []
    for snap in data["lines"]:
        line = existing.get(snap["id"]) or RecipeIngredient()
        for f in LINE_FIELDS:
            setattr(line, f, snap[f])
        if line.ingredient_id not in known:   # varen er slettet i kataloget siden
            line.ingredient_id, line.match_status = None, "ingen"
        if line.id is None:
            recipe.ingredients.append(line)
        keep.append(line)
    recipe.ingredients[:] = keep
    session.flush()


# --- Katalog ---------------------------------------------------------------------------


def ingredient_state(ing: Ingredient) -> dict:
    return {"name": ing.name, "department": ing.department, "pantry": ing.pantry,
            "grams_per_piece": ing.grams_per_piece, "grams_per_dl": ing.grams_per_dl}


def record_change(session: Session, user_id: int | None, kind: str, ingredient_id: int | None, summary: str,
                  before: dict | None = None, after: dict | None = None) -> CatalogChange:
    change = CatalogChange(user_id=user_id, kind=kind, ingredient_id=ingredient_id, summary=summary[:300],
                           before=json.dumps(before or {}, ensure_ascii=False),
                           after=json.dumps(after or {}, ensure_ascii=False))
    session.add(change)
    session.flush()
    return change


class CannotUndo(Exception):
    pass


def undo_change(session: Session, change: CatalogChange) -> str:
    """Fortryd en rettelse. Kaster CannotUndo med en forklaring, hvis det ikke længere kan lade sig gøre."""
    before, after = json.loads(change.before or "{}"), json.loads(change.after or "{}")
    if change.undone:
        raise CannotUndo("Rettelsen er allerede fortrudt")
    if change.kind == "vare":
        ing = session.get(Ingredient, change.ingredient_id)
        if ing is None:
            raise CannotUndo("Varen findes ikke mere")
        for f in ("name", "department", "grams_per_piece", "grams_per_dl"):
            setattr(ing, f, before[f])
        msg = f"{after.get('name')} er sat tilbage til {before['name']}"
    elif change.kind == "vare_slettet":
        if session.scalar(select(Ingredient.id).where(Ingredient.name == before["name"])):
            raise CannotUndo("Der findes allerede en vare med det navn")
        ing = Ingredient(name=before["name"], department=before["department"], pantry=before.get("pantry", False),
                         grams_per_piece=before["grams_per_piece"], grams_per_dl=before["grams_per_dl"])
        session.add(ing)
        session.flush()
        for a in before.get("aliases", []):
            if not session.scalar(select(IngredientAlias.id).where(IngredientAlias.key == a["key"])):
                ing.aliases.append(IngredientAlias(alias=a["alias"], key=a["key"], source=a["source"]))
        msg = f"{ing.name} er oprettet igen"
    elif change.kind == "alias_slettet":
        if session.scalar(select(IngredientAlias.id).where(IngredientAlias.key == before["key"])):
            raise CannotUndo("Aliaset findes allerede")
        if session.get(Ingredient, before["ingredient_id"]) is None:
            raise CannotUndo("Varen findes ikke mere")
        session.add(IngredientAlias(alias=before["alias"], key=before["key"], ingredient_id=before["ingredient_id"],
                                    source=before["source"]))
        msg = f"Aliaset {before['alias']} er lagt tilbage"
    elif change.kind == "alias_tilfoejet":
        alias = session.scalar(select(IngredientAlias).where(IngredientAlias.key == after["key"]))
        if alias is None:
            raise CannotUndo("Aliaset findes ikke mere")
        session.delete(alias)
        msg = f"Aliaset {after['alias']} er fjernet"
    else:
        raise CannotUndo("Ukendt rettelse")
    change.undone = True
    return msg
