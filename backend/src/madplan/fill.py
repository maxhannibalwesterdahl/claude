"""Fyld ugen: vælger en ret til de ledige dage i en madplan.

Ren logik uden database. Kalderen (api/plans.py) finder kandidaterne og deres
hovedingredienser og sender dem her. Se `choose_days`.
"""

from dataclasses import dataclass
from datetime import date

ALTERNATIVES = 12


@dataclass(frozen=True)
class Option:
    """En kandidat i den rækkefølge, den skal bruges. `reason` er "ønske", "favorit" eller "længe siden"."""
    recipe_id: int
    reason: str


@dataclass(frozen=True)
class Pick:
    """Retten, der foreslås på en dag."""
    date: date
    recipe_id: int
    reason: str


def choose_days(
    days: list[date],
    options: list[Option],
    mains: dict[int, set[int]],
    planned_mains: set[int],
) -> tuple[list[Pick], list[Option]]:
    """Fordel kandidaterne over dagene i datorækkefølge.

    Første valg er den første kandidat, der ikke har en hovedingrediens til fælles med
    en ret, der allerede er på planen eller er valgt til en anden dag i ugen. Kan det
    ikke lade sig gøre, bruges en ny kandidat alligevel. Er alle brugt, står de
    sidste dage uden forslag: samme ret to gange i ugen foreslås ikke.

    `mains` viser hovedingredienserne pr. opskrift, og `planned_mains` er dem, der
    allerede er på planen. Returnerer forslagene og op til tolv reserver: de næste
    kandidater, der ikke er brugt.
    """
    used: set[int] = set()
    taken_mains = set(planned_mains)
    picks: list[Pick] = []
    for d in sorted(days):
        fresh = [o for o in options if o.recipe_id not in used]
        pick = next((o for o in fresh if not mains.get(o.recipe_id, set()) & taken_mains), None)
        pick = pick or next(iter(fresh), None)
        if pick is None:
            continue
        used.add(pick.recipe_id)
        taken_mains |= mains.get(pick.recipe_id, set())
        picks.append(Pick(date=d, recipe_id=pick.recipe_id, reason=pick.reason))
    alternatives = [o for o in options if o.recipe_id not in used][:ALTERNATIVES]
    return picks, alternatives
