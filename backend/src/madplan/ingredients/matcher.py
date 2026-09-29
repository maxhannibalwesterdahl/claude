"""Kobler et varenavn fra læseren til en vare i ingredienstabellen.

    "røde peberfrugter" -> peberfrugt (sikker)
    "timian" + enhed "tsk" -> tørret timian (sikker)
    "vaniljeskyr" -> skyr (usikker: kun sidste del af ordet matcher)

Gratis, regelbaseret udgave bag `IngredientMatcher`-grænsefladen, så den
senere kan suppleres med en AI-udgave (se docs/SPEC.md §4). Usikre match skal
bekræftes af brugeren, og brugerens rettelser bliver til nye aliaser.
"""

import re
import unicodedata
from dataclasses import dataclass, field
from importlib import resources
from typing import Literal, Protocol

Confidence = Literal["sikker", "usikker"]

DEPARTMENTS = {
    "fg": "Frugt & grønt",
    "brod": "Brød",
    "kod": "Kød & fisk",
    "mej": "Mejeri & køl",
    "frost": "Frost",
    "kol": "Kolonial",
    "kry": "Krydderier",
    "dri": "Drikkevarer",
    "andet": "Andet",
}

# Urter og krydderier, der findes både friske og tørrede. Uden "frisk"/"tørret"
# i teksten afgør enheden det: små måleenheder betyder tørret.
#   navn -> (frisk vare, tørret vare)
DUAL_HERBS = {
    "timian": ("frisk timian", "tørret timian"),
    "rosmarin": ("frisk rosmarin", "tørret rosmarin"),
    "oregano": ("frisk oregano", "tørret oregano"),
    "basilikum": ("frisk basilikum", "tørret basilikum"),
    "koriander": ("frisk koriander", "stødt koriander"),
}
DRIED_UNITS = {"tsk", "spsk", "knsp", "nip", "g"}

# Ord, der ikke ændrer hvilken vare det er.
_IGNORED_PREFIXES = ("økologiske ", "økologisk ", "øko ", "danske ", "dansk ")
_PERCENT_RE = re.compile(r"\s*\d+(?:[.,]\d+)?\s*%")
# Flertals- og bøjningsendelser, prøvet i rækkefølge.
_ENDINGS = ("erne", "ene", "er", "e", "r")
_MIN_SUFFIX = 4
_PLANT_PARTS = ("blade", "blad", "kviste", "kvist")


def _stems(k: str) -> list[str]:
    """Mulige entalsformer: "avocadoer" -> "avocado", "pastinakker" -> "pastinak",
    "fennikler" -> "fennikel"."""
    stems = []
    for ending in _ENDINGS:
        if k.endswith(ending) and len(k) - len(ending) >= 3:
            stem = k[: -len(ending)]
            stems.append(stem)
            if len(stem) >= 2 and stem[-1] == stem[-2]:  # dobbeltkonsonant
                stems.append(stem[:-1])
    if k.endswith("ler"):
        stems.append(k[:-3] + "el")
    return stems


@dataclass(frozen=True)
class Ingredient:
    name: str
    department: str
    pantry: bool
    aliases: tuple[str, ...] = field(default=(), compare=False)


@dataclass(frozen=True)
class Match:
    ingredient: Ingredient
    confidence: Confidence
    method: str


class IngredientMatcher(Protocol):
    def match(self, item: str, unit: str | None = None) -> Match | None: ...


def key(text: str) -> str:
    """Nøgle til opslag: små bogstaver, uden accenter, mellemrum og bindestreger."""
    text = text.lower().strip()
    # Fjern accenter (é -> e), men behold æ, ø og å.
    text = "".join(
        c for c in unicodedata.normalize("NFD", text)
        if unicodedata.category(c) != "Mn" or c in "̊"
    )
    text = unicodedata.normalize("NFC", text)
    return re.sub(r"[\s\-]", "", text)


def load_table(text: str | None = None) -> list[Ingredient]:
    if text is None:
        text = resources.files("madplan.ingredients").joinpath("data/ingredienser.txt").read_text("utf-8")
    table = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|")]
        parts += [""] * (4 - len(parts))
        name, dept, pantry, aliases = parts[:4]
        if dept not in DEPARTMENTS:
            raise ValueError(f"ukendt afdeling {dept!r} for {name!r}")
        alias_list = tuple(a.strip() for a in aliases.split(",") if a.strip())
        table.append(Ingredient(name, dept, pantry == "b", alias_list))
    return table


class RuleMatcher:
    def __init__(self, table: list[Ingredient] | None = None):
        self.table = table if table is not None else load_table()
        self.by_name = {i.name: i for i in self.table}
        self._index: dict[str, Ingredient] = {}
        for ing in self.table:
            for alias in (ing.name, *ing.aliases):
                k = key(alias)
                other = self._index.get(k)
                if other is not None and other is not ing:
                    raise ValueError(f"alias {alias!r} bruges af både {other.name!r} og {ing.name!r}")
                self._index[k] = ing
        # Længste først, så "flødeost" vælges før "ost".
        self._suffix_keys = sorted(
            (k for k in self._index if len(k) >= _MIN_SUFFIX), key=len, reverse=True
        )

    def add_alias(self, alias: str, ingredient_name: str) -> None:
        """Brugerens rettelse: fremover matches `alias` sikkert til varen."""
        self._index[key(alias)] = self.by_name[ingredient_name]

    def match(self, item: str, unit: str | None = None) -> Match | None:
        item = item.lower().strip()
        if not item:
            return None
        found = self._exact(item, unit)
        if found:
            return Match(found[0], "sikker", found[1])

        # Usikker 1: drop første ord ("kulørte chokoladeknapper").
        words = item.split()
        if len(words) > 1:
            found = self._exact(" ".join(words[1:]), unit)
            if found:
                return Match(found[0], "usikker", "uden første ord")

        # Usikker 2: sammensat ord, hvor sidste del er en kendt vare ("vaniljeskyr").
        # Kun for ét ord, ellers giver "pistaciekerner uden salt" -> salt.
        if len(words) > 1:
            return None
        k = key(item)
        for suffix in self._suffix_keys:
            if k.endswith(suffix) and len(k) - len(suffix) >= 3:
                return Match(self._index[suffix], "usikker", "sidste del af ordet")
        return None

    def _exact(self, item: str, unit: str | None) -> tuple[Ingredient, str] | None:
        for prefix in _IGNORED_PREFIXES:
            if item.startswith(prefix):
                item = item[len(prefix):]
        item = _PERCENT_RE.sub("", item).strip()

        herb = self._herb(item, unit)
        if herb:
            return herb, "urt efter enhed"

        k = key(item)
        if k in self._index:
            return self._index[k], "alias"
        for stem in _stems(k):
            if stem in self._index:
                return self._index[stem], "bøjning"
        # "basilikumblade", "rosmarinkviste": planten før bladene.
        for part in _PLANT_PARTS:
            if k.endswith(part) and len(k) - len(part) >= 3:
                found = self._exact(item[: -len(part)], unit or "bundt")
                if found:
                    return found[0], "urt uden blade"
        return None

    def _herb(self, item: str, unit: str | None) -> Ingredient | None:
        if item not in DUAL_HERBS:
            return None
        fresh, dried = DUAL_HERBS[item]
        return self.by_name[dried if unit in DRIED_UNITS else fresh]
