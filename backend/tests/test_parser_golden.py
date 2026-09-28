"""Måler læseren mod håndskrevet facit for rigtige danske opskriftslinjer.

Mål fra fase 0 i docs/PLAN.md: mindst 90 % korrekte. Alle tre sæt er nu brugt
til at rette læseren, så de virker som regressionstest. Den ærlige, blinde
måling står i docs/fase0-ingredienslaeser.md.
"""

import pytest
from golden import SETS, evaluate, load_golden, load_raw_lines

from madplan.ingredients import DanishRuleParser

TARGET = 0.90


@pytest.mark.parametrize("dataset", SETS)
def test_golden_covers_raw_lines(dataset):
    golden_file, raw_files = SETS[dataset]
    golden = load_golden(golden_file)
    lines = load_raw_lines(raw_files)
    assert len(golden) >= 200
    assert all(line in golden for line in lines if dataset != "blind")


@pytest.mark.parametrize("dataset", SETS)
def test_accuracy(dataset):
    unique_rate, _, failures = evaluate(DanishRuleParser(), dataset)
    report = "\n".join(
        f"  {raw!r}: fik ({p.quantity}, {p.unit}, {p.item!r}) ventede {exp}"
        for raw, p, exp in failures
    )
    assert unique_rate >= TARGET, f"{dataset}: {unique_rate:.1%} korrekte\n{report}"
