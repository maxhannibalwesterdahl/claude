"""Fælles typer for ingredienslæsning.

Resten af appen afhænger kun af `IngredientParser` og `ParsedIngredient`, så den
regelbaserede læser senere kan udskiftes med fx en AI-baseret uden andre
ændringer (se docs/SPEC.md §4).
"""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ParsedIngredient:
    raw: str
    quantity: float | None
    unit: str | None
    item: str
    note: str | None = None
    # Øvre grænse for intervaller som "2-3 løg". None hvis ikke et interval.
    quantity_max: float | None = None


class IngredientParser(Protocol):
    def parse(self, line: str) -> ParsedIngredient: ...
