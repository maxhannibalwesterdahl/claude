import subprocess
import sys
from pathlib import Path

import pytest

from madplan.ingredients.matcher import RuleMatcher, key, load_table

ROOT = Path(__file__).resolve().parents[1]
m = RuleMatcher()


def name(item, unit=None):
    r = m.match(item, unit)
    return (r.ingredient.name, r.confidence) if r else None


def test_table_loads_without_duplicate_aliases():
    assert len(load_table()) > 200


def test_key_ignores_spaces_hyphens_and_accents():
    assert key("Crème fraîche") == key("cremefraiche")
    assert key("hoisin sauce") == key("hoisinsauce")
    assert key("æble") != key("able")


@pytest.mark.parametrize(
    "item, unit, expected",
    [
        ("øko citron", None, "citron"),
        ("citronsaft", "spsk", "citron"),
        ("avocadoer", None, "avocado"),
        ("pastinakker", None, "pastinak"),
        ("fennikler", None, "fennikel"),
        ("cremefraiche 18 %", "dl", "creme fraiche"),
        ("timian", "tsk", "tørret timian"),
        ("timian", "bundt", "frisk timian"),
        ("koriander", "tsk", "stødt koriander"),
        ("koriander", None, "frisk koriander"),
        ("basilikumblade", "dl", "frisk basilikum"),
    ],
)
def test_sure_matches(item, unit, expected):
    assert name(item, unit) == (expected, "sikker")


def test_compound_word_is_uncertain():
    assert name("vaniljeskyr") == ("skyr", "usikker")


def test_multiword_phrase_does_not_match_on_last_word_suffix():
    # Tidligere fejl: "pistaciekerner uden salt" -> salt
    r = m.match("pistaciekerner uden salt")
    assert r is None or r.ingredient.name != "salt"


def test_unknown_returns_none():
    assert name("atamon") is None


def test_user_correction_becomes_sure():
    local = RuleMatcher()
    local.add_alias("frilandsæg", "æg")
    assert local.match("frilandsæg").ingredient.name == "æg"


@pytest.mark.parametrize("labels", ["blind_matches.tsv", "cover_matches.tsv"])
def test_no_confident_wrong_matches(labels):
    out = subprocess.run(
        [sys.executable, "scripts/matcher_report.py", f"tests/data/{labels}"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout
    wrong = next(line for line in out.splitlines() if "FORKERT" in line and "%" in line)
    assert wrong.split()[1] == "0", out
