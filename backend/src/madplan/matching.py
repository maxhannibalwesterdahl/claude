"""Familiens varekobling: et lag oven på de fælles ingrediens­linjer og aliaser.

Familiens rettelser ("fløde" = piskefløde, "denne linje er ikke en vare") gælder kun
familien selv og ændrer aldrig de fælles opskrifter eller det fælles katalog, som kun
systemadmin retter (docs/flere-familier.md §3-4). Rækkefølgen er:

1. familiens valg for netop denne linje (`household_line_match`)
2. familiens valg for varenavnet (`household_ingredient_pref`)
3. linjens egen vare i den fælles opskrift
"""

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from .ingredients import matcher as m
from .models import (
    HouseholdIngredientPref,
    HouseholdLineMatch,
    HouseholdRecipe,
    Ingredient,
    Recipe,
    RecipeIngredient,
)


@dataclass
class Overlay:
    line: dict[int, tuple[int | None, str]] = field(default_factory=dict)
    pref: dict[str, int] = field(default_factory=dict)

    @classmethod
    def load(cls, session: Session, household_id: int) -> "Overlay":
        return cls(
            line={r.line_id: (r.ingredient_id, r.match_status)
                  for r in session.scalars(select(HouseholdLineMatch).where(HouseholdLineMatch.household_id == household_id))},
            pref={r.key: r.ingredient_id
                  for r in session.scalars(select(HouseholdIngredientPref).where(HouseholdIngredientPref.household_id == household_id))
                  if r.ingredient_id is not None},
        )

    def resolve(self, line: RecipeIngredient) -> tuple[int | None, str]:
        """(vare-id, status) for linjen set fra familien."""
        if line.id in self.line:
            return self.line[line.id]
        pref = self.pref.get(m.key(line.item)) if line.item else None
        if pref is not None:
            return pref, "sikker"
        return line.ingredient_id, line.match_status


def ingredient_map(session: Session) -> dict[int, Ingredient]:
    return {i.id: i for i in session.scalars(select(Ingredient))}


def set_line_match(session: Session, household_id: int, line_id: int, ingredient_id: int | None) -> None:
    """Familiens valg for én linje. `ingredient_id=None`: linjen er bevidst ikke en vare."""
    row = session.scalar(select(HouseholdLineMatch).where(
        HouseholdLineMatch.household_id == household_id, HouseholdLineMatch.line_id == line_id))
    if row is None:
        session.add(HouseholdLineMatch(household_id=household_id, line_id=line_id,
                                       ingredient_id=ingredient_id, match_status="bekræftet"))
    else:
        row.ingredient_id, row.match_status = ingredient_id, "bekræftet"


def learn_preference(session: Session, household_id: int, item: str, ingredient: Ingredient) -> int:
    """Familien har koblet `item` til en vare: husk det for familien, og tæl de linjer i
    familiens opskrifter, der nu følger det. Svarer med antal linjer, der blev ændret.

    Er `item` navnet på en ANDEN vare ("løg" bekræftet som rødløg), gælder valget kun den
    ene linje (det er allerede gemt som linjevalg), så ét valg ikke omdøber en vare."""
    k = m.key(item)
    if not k:
        return 0
    owner = next((i for i in session.scalars(select(Ingredient)) if m.key(i.name) == k), None)
    if owner is not None and owner.id != ingredient.id:
        return 0
    row = session.scalar(select(HouseholdIngredientPref).where(
        HouseholdIngredientPref.household_id == household_id, HouseholdIngredientPref.key == k))
    if owner is not None:
        # Varens eget navn: et tidligere valg af en anden vare for det navn fortrydes.
        if row is not None:
            session.delete(row)
        return 0
    if row is None:
        session.add(HouseholdIngredientPref(household_id=household_id, key=k, ingredient_id=ingredient.id))
    else:
        row.ingredient_id = ingredient.id
    session.flush()
    overlay = Overlay.load(session, household_id)
    mine = select(HouseholdRecipe.recipe_id).where(HouseholdRecipe.household_id == household_id)
    changed = 0
    for line in session.scalars(select(RecipeIngredient).join(Recipe).where(
            (Recipe.id.in_(mine)) | (Recipe.created_by_household == household_id))):
        if m.key(line.item) == k and line.id not in overlay.line and (line.ingredient_id, line.match_status) != (ingredient.id, "sikker"):
            changed += 1
    return changed
