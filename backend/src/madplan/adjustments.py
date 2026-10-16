"""Familiens tilpasninger af fælles opskrifter, samlet pr. opskrift."""

from collections import defaultdict
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import HouseholdRecipeAdjustment


@dataclass
class Adjustments:
    skip: set[int] = field(default_factory=set)
    quantity: dict[int, float] = field(default_factory=dict)
    extras: list[HouseholdRecipeAdjustment] = field(default_factory=list)
    note: str = ""


def load_adjustments(session: Session, household_id: int, recipe_ids: list[int] | set[int]) -> dict[int, Adjustments]:
    out: dict[int, Adjustments] = defaultdict(Adjustments)
    if not recipe_ids:
        return out
    rows = session.scalars(
        select(HouseholdRecipeAdjustment)
        .where(HouseholdRecipeAdjustment.household_id == household_id,
               HouseholdRecipeAdjustment.recipe_id.in_(list(recipe_ids)))
        .order_by(HouseholdRecipeAdjustment.id)
    )
    for a in rows:
        adj = out[a.recipe_id]
        if a.type == "skip" and a.line_id is not None:
            adj.skip.add(a.line_id)
        elif a.type == "quantity" and a.line_id is not None and a.quantity is not None:
            adj.quantity[a.line_id] = a.quantity
        elif a.type == "extra":
            adj.extras.append(a)
        elif a.type == "note":
            adj.note = a.value
    return out


def parse_extras(session: Session, household_id: int, adjust: dict[int, Adjustments]) -> dict:
    """Familiens ekstra linjer læst som ingredienslinjer: tilpasnings-id -> (læst linje, vare eller None)."""
    from .catalog import Catalog

    extras = [a for adj in adjust.values() for a in adj.extras]
    if not extras:
        return {}
    catalog = Catalog(session, household_id)
    out = {}
    for a in extras:
        p = catalog.parse(a.value)
        out[a.id] = (p, catalog.by_id.get(p.ingredient_id) if p.match_status in ("sikker", "bekræftet") else None)
    return out
