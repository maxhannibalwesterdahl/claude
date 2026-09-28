"""Ingredienstabellen i databasen: startdata, læsning af linjer og læring.

Startdata kommer fra ingredients/data/ingredienser.txt og omregninger.txt og
lægges ind ved opstart. Kun manglende varer og aliaser tilføjes, så brugerens
egne ændringer bevares.
"""

from dataclasses import dataclass
from importlib import resources

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .ingredients import DanishRuleParser
from .ingredients import matcher as m
from .models import Ingredient, IngredientAlias, RecipeIngredient

parser = DanishRuleParser()


def load_conversions(text: str | None = None) -> dict[str, tuple[float | None, float | None]]:
    if text is None:
        text = resources.files("madplan.ingredients").joinpath("data/omregninger.txt").read_text("utf-8")
    out = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name, per_piece, per_dl = ([p.strip() for p in line.split("|")] + ["", ""])[:3]
        out[name] = (float(per_piece) if per_piece else None, float(per_dl) if per_dl else None)
    return out


def sync_seed(session: Session) -> int:
    """Læg manglende startvarer og aliaser ind. Returnerer antal nye varer."""
    existing = {i.name: i for i in session.scalars(select(Ingredient))}
    keys = set(session.scalars(select(IngredientAlias.key)))
    conversions = load_conversions()
    added = 0
    table = m.load_table()
    unknown = set(conversions) - {seed.name for seed in table}
    if unknown:
        raise ValueError(f"omregninger.txt nævner ukendte varer: {sorted(unknown)}")
    for seed in table:
        ing = existing.get(seed.name)
        if ing is None and m.key(seed.name) in keys:
            continue  # omdøbt af brugeren; det gamle navn er et alias
        if ing is None:
            per_piece, per_dl = conversions.get(seed.name, (None, None))
            ing = Ingredient(
                name=seed.name, department=seed.department, pantry=seed.pantry,
                grams_per_piece=per_piece, grams_per_dl=per_dl,
            )
            session.add(ing)
            existing[seed.name] = ing
            added += 1
        for alias in seed.aliases:
            k = m.key(alias)
            if k not in keys and k != m.key(seed.name):
                ing.aliases.append(IngredientAlias(alias=alias, key=k, source="seed"))
                keys.add(k)
    session.commit()
    return added


class Catalog:
    """Matcher bygget ud fra databasen. Bygges pr. anmodning (få hundrede varer)."""

    def __init__(self, session: Session):
        rows = session.scalars(select(Ingredient).options(selectinload(Ingredient.aliases))).all()
        self.by_id = {i.id: i for i in rows}
        self._id_by_name = {i.name: i.id for i in rows}
        table = [
            m.Ingredient(i.name, i.department, i.pantry, tuple(a.alias for a in i.aliases if a.source == "seed"))
            for i in rows
        ]
        self.matcher = m.RuleMatcher(table)
        # Brugerens rettelser vinder over startdata.
        for i in rows:
            for a in i.aliases:
                if a.source == "user":
                    self.matcher.add_alias(a.alias, i.name)

    def parse(self, line: str) -> "ParsedLine":
        p = parser.parse(line)
        found = self.matcher.match(p.item, p.unit) if p.item else None
        return ParsedLine(
            raw=line.strip(),
            quantity=p.quantity,
            quantity_max=p.quantity_max,
            unit=p.unit,
            item=p.item,
            note=p.note,
            ingredient_id=self._id_by_name[found.ingredient.name] if found else None,
            match_status=found.confidence if found else "ingen",
        )


@dataclass
class ParsedLine:
    raw: str
    quantity: float | None
    quantity_max: float | None
    unit: str | None
    item: str
    note: str | None
    ingredient_id: int | None
    match_status: str


def learn_alias(session: Session, item: str, ingredient: Ingredient) -> int:
    """Brugeren har koblet `item` til en vare. Husk det, og ret alle andre
    ubekræftede linjer med samme varenavn. Returnerer antal rettede linjer."""
    k = m.key(item)
    if not k:
        return 0
    if k != m.key(ingredient.name):
        alias = session.scalar(select(IngredientAlias).where(IngredientAlias.key == k))
        if alias is None:
            session.add(IngredientAlias(alias=item.lower().strip(), key=k, ingredient=ingredient, source="user"))
        else:
            alias.ingredient = ingredient
            alias.source = "user"
    changed = 0
    for line in session.scalars(select(RecipeIngredient).where(RecipeIngredient.match_status != "bekræftet")):
        if m.key(line.item) == k:
            line.ingredient_id = ingredient.id
            line.match_status = "sikker"
            changed += 1
    return changed


def rematch_open_lines(session: Session, catalog: "Catalog | None" = None) -> int:
    """Match linjer uden sikker vare igen, fx efter nye varer i tabellen.
    Bekræftede linjer røres ikke. Returnerer antal linjer, der fik en vare."""
    catalog = catalog or Catalog(session)
    changed = 0
    open_lines = session.scalars(
        select(RecipeIngredient).where(RecipeIngredient.match_status.in_(("ingen", "usikker")))
    )
    for line in open_lines:
        found = catalog.matcher.match(line.item, line.unit) if line.item else None
        if found and found.confidence == "sikker":
            line.ingredient_id = catalog._id_by_name[found.ingredient.name]
            line.match_status = "sikker"
            changed += 1
    return changed


# --- Hovedingredienser -----------------------------------------------------

_GRAMS_PER_UNIT = {"g": 1.0, "kg": 1000.0}
_DL_PER_UNIT = {"dl": 1.0, "l": 10.0, "cl": 0.1, "ml": 0.01}


def grams(quantity: float | None, unit: str | None, ing: Ingredient) -> float | None:
    """Omtrentlig vægt af en linje, hvis den kan regnes ud."""
    if quantity is None:
        return None
    if unit in _GRAMS_PER_UNIT:
        return quantity * _GRAMS_PER_UNIT[unit]
    if unit in _DL_PER_UNIT and ing.grams_per_dl:
        return quantity * _DL_PER_UNIT[unit] * ing.grams_per_dl
    if unit is None and ing.grams_per_piece:
        return quantity * ing.grams_per_piece
    return None


def suggest_main(lines: list[RecipeIngredient], by_id: dict[int, Ingredient]) -> None:
    """Foreslå 1-2 hovedingredienser: kød og fisk først, ellers den tungeste vare."""
    candidates = []
    for line in lines:
        line.is_main = False
        ing = by_id.get(line.ingredient_id) if line.ingredient_id else None
        if ing is None or ing.pantry:
            continue
        candidates.append((line, ing, grams(line.quantity, line.unit, ing) or 0.0))

    meat = [c for c in candidates if c[1].department == "kod"]
    pool, limit = (meat, 2) if meat else ([c for c in candidates if c[2] > 0], 1)
    chosen: set[int] = set()
    for line, ing, _ in sorted(pool, key=lambda c: c[2], reverse=True):
        if ing.id in chosen:
            continue
        line.is_main = True
        chosen.add(ing.id)
        if len(chosen) == limit:
            break
