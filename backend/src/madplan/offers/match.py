"""Finder de varer i ingredienstabellen, som et tilbud dækker.

    "Hakket okse-, grise- eller grise/kalvekød"
    -> hakket oksekød, hakket svinekød   (blandingsfars matcher ikke)

Tilbudstekster er korte og fulde af mærkenavne ("Dava danske frilandsæg"),
så teksten deles i alternativer, og hvert alternativ prøves med og uden de
forreste ord.
"""

import re
from dataclasses import dataclass

from madplan.ingredients.matcher import Confidence, Ingredient, IngredientMatcher

# Sidste led i sammensatte ord, der deles i avisen: "okse-, grisekød".
_HEADS = sorted(
    ["kød", "filet", "fileter", "bryst", "lår", "overlår", "pølser", "ost", "røget", "brød", "mælk"],
    key=len,
    reverse=True,
)
_SPLIT_RE = re.compile(r",\s*|\s+eller\s+")
_CUT_WORDS = (" af ", " med ")


@dataclass(frozen=True)
class OfferMatch:
    ingredient: Ingredient
    confidence: Confidence
    phrase: str


def _alternatives(heading: str) -> list[str]:
    text = heading.lower().replace("&", " og ").strip()
    parts = [p.strip() for p in _SPLIT_RE.split(text) if p.strip()]
    if not parts:
        return []

    # "-inderfilet": forkortet efter forrige alternativ. Springes over.
    parts = [p for p in parts if not p.startswith("-")]
    if not parts:
        return []

    # "okse-" får sidste led fra det sidste alternativ ("grisekød" -> "oksekød").
    last_words = parts[-1].split()
    expanded = []
    for p in parts:
        if p.endswith("-"):
            stem = p[:-1]
            for i, w in enumerate(last_words):
                head = next((h for h in _HEADS if w.endswith(h) and len(w) > len(h)), None)
                if head:
                    p = " ".join([stem + head, *last_words[i + 1:]])
                    break
            else:
                continue
        expanded.append(p)

    # "Hakket okse-, grise- eller ..." : "hakket" gælder alle alternativer.
    first = expanded[0].split()[0] if expanded else ""
    if first in {"hakket", "hakkede"}:
        expanded = [p if p.startswith(first) else f"{first} {p}" for p in expanded]
    return expanded


def _candidates(phrase: str) -> list[tuple[str, bool]]:
    """(kandidat, hele_frasen): hele frasen, frasen før "af"/"med", og begge
    uden de forreste ord. Kun hele frasen kan give et sikkert match; fjernede
    ord kan være mærkenavne ("Dava"), men også vigtige ("varmrøget laks")."""
    bases = [phrase]
    for cut in _CUT_WORDS:
        if cut in phrase:
            bases.append(phrase.split(cut, 1)[0])
    out = []
    for base in bases:
        words = base.split()
        out += [(" ".join(words[i:]), i == 0) for i in range(len(words))]
    return out


def match_offer(heading: str, matcher: IngredientMatcher) -> list[OfferMatch]:
    found: dict[str, OfferMatch] = {}
    for phrase in _alternatives(heading):
        if "/" in phrase:  # blandingsprodukt, fx "okse/grisekød"
            continue
        best = None
        for cand, whole in _candidates(phrase):
            m = matcher.match(cand)
            if m and m.confidence == "sikker" and whole:
                best = OfferMatch(m.ingredient, "sikker", phrase)
                break
            if m and best is None:
                best = OfferMatch(m.ingredient, "usikker", phrase)
        if best and (best.ingredient.name not in found or best.confidence == "sikker"):
            found[best.ingredient.name] = best
    return list(found.values())
