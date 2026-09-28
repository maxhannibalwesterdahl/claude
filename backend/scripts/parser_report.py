"""Udskriver læserens træfsikkerhed og fejl for et testsæt.

    python scripts/parser_report.py holdout
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests"))

from golden import evaluate  # noqa: E402

from madplan.ingredients import DanishRuleParser  # noqa: E402

dataset = sys.argv[1] if len(sys.argv) > 1 else "valdemarsro"
unique_rate, all_rate, failures = evaluate(DanishRuleParser(), dataset)
print(f"{dataset}: {unique_rate:.1%} af unikke linjer, {all_rate:.1%} af alle linjer, {len(failures)} fejl")
for raw, p, (qty, unit, item) in failures:
    print(f"  {raw}\n      fik     ({p.quantity}, {p.unit}, {p.item!r})\n      ventede ({qty}, {unit}, {item!r})")
