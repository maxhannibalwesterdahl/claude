"""Måler tilbudsmatchning mod håndskrevet facit.

    python scripts/offer_report.py tests/data/bilka_offers_2026-09-28.json tests/data/bilka_offer_matches.tsv
"""

import json
import sys

from madplan.ingredients.matcher import RuleMatcher
from madplan.offers.match import match_offer

offers_path, labels_path = sys.argv[1], sys.argv[2]
expected: dict[str, set[str]] = {}
for line in open(labels_path, encoding="utf-8"):
    if line.startswith("#") or not line.strip():
        continue
    heading, names = line.rstrip("\n").split("\t")
    expected[heading] = {n.strip() for n in names.split(",") if n.strip()}

m = RuleMatcher()
unknown = {n for s in expected.values() for n in s if n not in m.by_name}
if unknown:
    sys.exit(f"facit nævner ukendte varer: {unknown}")

headings = sorted({o["heading"] for o in json.load(open(offers_path, encoding="utf-8"))})
missing = set(expected) - set(headings)
if missing:
    sys.exit(f"facit nævner tilbud, der ikke findes: {missing}")

tp = {"sikker": 0, "usikker": 0}
fp = {"sikker": 0, "usikker": 0}
fn = 0
lines = []
for h in headings:
    exp = expected.get(h, set())
    got = {r.ingredient.name: r for r in match_offer(h, m)}
    for name, r in got.items():
        if name in exp:
            tp[r.confidence] += 1
        else:
            fp[r.confidence] += 1
            lines.append(f"  [FORKERT {r.confidence}] {h!r} -> {name} (via {r.phrase!r})")
    for name in exp - got.keys():
        fn += 1
        lines.append(f"  [MANGLER] {h!r} -> {name}")

total_exp = sum(len(s) for s in expected.values())
print(f"{len(headings)} tilbud, {len(expected)} med relevante varer, {total_exp} forventede match")
print(f"  fundet sikkert:      {tp['sikker']}")
print(f"  fundet usikkert:     {tp['usikker']}")
print(f"  mangler:             {fn}")
print(f"  forkert sikkert:     {fp['sikker']}")
print(f"  forkert usikkert:    {fp['usikker']}")
print("\n".join(lines))
