"""Sammenlægning af mængder til indkøbslisten. Se docs/SPEC.md §3.5.

Samme vare lægges sammen på tværs af dage og inden for samme opskrift:

  - Samme enhed summeres direkte: 1 dåse + 1 dåse = 2 dåse.
  - Forskellige enheder omregnes, hvis varen har omregninger:
    "2 løg" + "150 g løg" = 3 stk (150 g pr. stk).
  - Stk, dåser, pakker osv. rundes op til hele. Vægt vises i g/kg, rumfang i ml/dl/l.
  - Kan det ikke omregnes, vises delene hver for sig: 1 bundt + 2 spsk.
  - Intervaller ("2-3 løg") bruger den højeste værdi, så der købes nok.
"""

import math
from dataclasses import dataclass

from .planning import PIECE_UNITS

MASS_G = {"g": 1.0, "kg": 1000.0}
VOLUME_ML = {"ml": 1.0, "cl": 10.0, "dl": 100.0, "l": 1000.0, "tsk": 5.0, "spsk": 15.0}
PIECE = {None, "stk"}  # tælles som stk og kan omregnes med g/stk
# Købes i hele enheder: 1,5 dåse bliver 2 dåser. Samme liste som madplanen bruger.
WHOLE = PIECE_UNITS | PIECE


@dataclass(frozen=True)
class Amount:
    quantity: float
    unit: str | None  # None = stk


def _nice(q: float) -> float:
    """Fjern flydende-komma-støj: 0.30000000000000004 -> 0.3"""
    return round(q, 3)


def _mass(grams: float) -> Amount:
    return Amount(_nice(grams / 1000), "kg") if grams >= 1000 else Amount(_nice(grams), "g")


def _volume(ml: float) -> Amount:
    if ml >= 1000:
        return Amount(_nice(ml / 1000), "l")
    if ml >= 100:
        return Amount(_nice(ml / 100), "dl")
    return Amount(_nice(ml), "ml")


def combine(
    parts: list[tuple[float, str | None]],
    grams_per_piece: float | None = None,
    grams_per_dl: float | None = None,
) -> list[Amount]:
    """Læg (mængde, enhed) sammen for én vare. Mængder uden tal skal ikke med."""
    if not parts:
        return []
    units = {u if u not in PIECE else None for _, u in parts}
    if len(units) == 1:
        # Én enhed: summér direkte og behold enheden (3 spsk, 2 dåse).
        unit = units.pop()
        total = sum(q for q, _ in parts)
        if unit in WHOLE:
            return [Amount(float(math.ceil(total - 1e-9)), unit)]
        if unit in MASS_G:
            return [_mass(total * MASS_G[unit])]
        if unit in ("ml", "cl", "dl", "l"):
            return [_volume(total * VOLUME_ML[unit])]
        return [Amount(_nice(total), unit)]

    pieces = grams = ml = 0.0
    has_pieces = has_grams = has_ml = False
    other: dict[str, float] = {}
    for q, u in parts:
        if u in PIECE:
            pieces += q
            has_pieces = True
        elif u in MASS_G:
            grams += q * MASS_G[u]
            has_grams = True
        elif u in VOLUME_ML:
            ml += q * VOLUME_ML[u]
            has_ml = True
        else:
            other[u] = other.get(u, 0.0) + q

    # Rumfang -> vægt, hvis der også er vægt eller stk at lægge det sammen med.
    if has_ml and grams_per_dl and (has_grams or (has_pieces and grams_per_piece)):
        grams += ml / 100 * grams_per_dl
        has_grams, ml, has_ml = True, 0.0, False
    # Vægt -> stk, når der er stk i forvejen ("2 løg" + "150 g løg").
    if has_grams and has_pieces and grams_per_piece:
        pieces += grams / grams_per_piece
        grams, has_grams = 0.0, False

    out = []
    if has_pieces:
        out.append(Amount(float(math.ceil(pieces - 1e-9)), None))
    if has_grams:
        out.append(_mass(grams))
    if has_ml:
        out.append(_volume(ml))
    out += [Amount(float(math.ceil(q - 1e-9)) if u in WHOLE else _nice(q), u) for u, q in sorted(other.items())]
    return out
