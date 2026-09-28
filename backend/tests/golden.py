"""Indlæsning af facitlisten og sammenligning, delt af test og rapport-script."""

import json
from pathlib import Path

from madplan.ingredients import IngredientParser, ParsedIngredient

DATA = Path(__file__).parent / "data"


def load_golden(name: str = "golden_lines.tsv") -> dict[str, tuple[float | None, str | None, str]]:
    golden = {}
    for line in (DATA / name).read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        raw, qty, unit, item = line.split("\t")
        golden[raw] = (float(qty) if qty else None, unit or None, item)
    return golden


SETS = {
    "valdemarsro": ("golden_lines.tsv", ["valdemarsro_raw.json"]),
    "holdout": ("holdout_lines.tsv", ["holdout_madensverden.json", "holdout_arla.json"]),
    "blind": ("blind_lines.tsv", ["blind_valdemarsro.json", "blind_madensverden.json", "blind_arla.json"]),
}


def load_raw_lines(files: list[str]) -> list[str]:
    lines = []
    for name in files:
        recipes = json.loads((DATA / name).read_text(encoding="utf-8"))
        lines += [line for r in recipes for line in r["ingredients"]]
    return lines


def matches(parsed: ParsedIngredient, expected: tuple[float | None, str | None, str]) -> bool:
    qty, unit, item = expected
    same_qty = (parsed.quantity is None and qty is None) or (
        parsed.quantity is not None and qty is not None and abs(parsed.quantity - qty) < 1e-6
    )
    return same_qty and parsed.unit == unit and parsed.item == item


def evaluate(
    parser: IngredientParser, dataset: str = "valdemarsro"
) -> tuple[float, float, list[tuple[str, ParsedIngredient, tuple]]]:
    """Returnerer (andel korrekte unikke linjer, andel korrekte af alle linjer, fejl)."""
    golden_file, raw_files = SETS[dataset]
    golden = load_golden(golden_file)
    failures = []
    for raw, expected in golden.items():
        parsed = parser.parse(raw)
        if not matches(parsed, expected):
            failures.append((raw, parsed, expected))
    failed = {f[0] for f in failures}
    all_lines = [line for line in load_raw_lines(raw_files) if line in golden]
    unique_rate = 1 - len(failures) / len(golden)
    all_rate = sum(1 for line in all_lines if line not in failed) / len(all_lines)
    return unique_rate, all_rate, failures
