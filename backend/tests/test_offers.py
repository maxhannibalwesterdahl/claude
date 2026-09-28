import json
from pathlib import Path

import pytest

from madplan.ingredients.matcher import RuleMatcher
from madplan.offers.match import _alternatives, match_offer
from madplan.offers.tjek import _FOOD_CATALOG_RE

DATA = Path(__file__).parent / "data"
m = RuleMatcher()


def test_hyphen_compounds_are_expanded():
    alts = _alternatives("Hakket okse-, grise- eller grise/kalvekød")
    assert alts == ["hakket oksekød", "hakket grisekød", "hakket grise/kalvekød"]


def test_mixed_mince_does_not_match():
    assert match_offer("Hakket okse/grisekød", m) == []


def test_offer_with_brand_is_uncertain():
    [r] = match_offer("Zucchi ekstra jomfru olivenolie", m)
    assert (r.ingredient.name, r.confidence) == ("olivenolie", "usikker")


@pytest.mark.parametrize(
    "label, food",
    [
        ("Bilka Food Uge 40 2026 - Fødevarer & Personlig Pleje", True),
        ("Bilka Nonfood Uge 40 2026 - Elektronik, Bolig, Have & Tekstil", False),
        ("Bilka Halloween 2026", False),
    ],
)
def test_food_catalog_filter(label, food):
    assert bool(_FOOD_CATALOG_RE.search(label)) == food


def test_week_snapshot_regression():
    """Uge 40 2026: mindst 65 % af de relevante varer findes, højst ét sikkert fejlmatch."""
    expected = {}
    for line in (DATA / "bilka_offer_matches.tsv").read_text("utf-8").splitlines():
        if line.startswith("#") or not line.strip():
            continue
        heading, names = line.split("\t")
        expected[heading] = {n.strip() for n in names.split(",")}
    offers = json.loads((DATA / "bilka_food_offers_2026-09-28.json").read_text("utf-8"))
    found = sure_wrong = 0
    for heading in {o["heading"] for o in offers}:
        exp = expected.get(heading, set())
        for r in match_offer(heading, m):
            if r.ingredient.name in exp:
                found += 1
            elif r.confidence == "sikker":
                sure_wrong += 1
    total = sum(len(s) for s in expected.values())
    assert found / total >= 0.65
    assert sure_wrong <= 1
