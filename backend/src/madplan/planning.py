"""Mængder i madplanen. Se docs/SPEC.md §3.3.

En opskrift er ét familiemåltid. Hver ret i planen har en gange-knap (×½, ×1,
×2). Ved ×½ rundes styk-enheder op til hele tal: "1 dåse" bliver 1, ikke ½.
"""

import math

MULTIPLIERS = (0.5, 1.0, 2.0)

# Enheder, der købes i hele stk. None = ingen enhed ("2 løg").
PIECE_UNITS = {None, "dåse", "pakke", "pose", "glas", "bakke", "potte", "bundt", "fed", "plade"}


def scale(quantity: float | None, unit: str | None, multiplier: float) -> float | None:
    if quantity is None:
        return None
    q = quantity * multiplier
    if multiplier < 1 and unit in PIECE_UNITS:
        return float(math.ceil(q - 1e-9))
    return q
