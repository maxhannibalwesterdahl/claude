"""Måler koblingen af varenavne mod håndskrevet facit.

    python scripts/matcher_report.py tests/data/blind_matches.tsv

Udfald pr. vare:
  korrekt          rigtig vare (eller korrekt intet match)
  usikker-rigtig   rigtig vare, men markeret usikker (brugeren bekræfter)
  usikker-forkert  forkert vare, men markeret usikker (brugeren afviser)
  mangler          intet match, men der fandtes en passende vare
  FORKERT          forkert vare markeret sikker (den farlige fejl)
"""

import collections
import sys

from madplan.ingredients.matcher import RuleMatcher

path = sys.argv[1]
rows = []
for line in open(path, encoding="utf-8"):
    if line.startswith("#") or not line.strip():
        continue
    item, unit, expected = line.rstrip("\n").split("\t")
    rows.append((item, unit or None, None if expected == "-" else expected))

m = RuleMatcher()
unknown = [e for _, _, e in rows if e and e not in m.by_name]
if unknown:
    sys.exit(f"facit nævner varer, der ikke findes i tabellen: {unknown}")

outcomes = collections.Counter()
details = collections.defaultdict(list)
for item, unit, expected in rows:
    r = m.match(item, unit)
    got = r.ingredient.name if r else None
    if r is None:
        o = "korrekt" if expected is None else "mangler"
    elif r.confidence == "sikker":
        o = "korrekt" if got == expected else "FORKERT"
    else:
        o = "usikker-rigtig" if got == expected else "usikker-forkert"
    outcomes[o] += 1
    if o != "korrekt":
        details[o].append(f"{item!r} ({unit}) -> {got} [{r.method if r else ''}], ventede {expected}")

n = len(rows)
print(f"{n} varer")
for o in ("korrekt", "usikker-rigtig", "usikker-forkert", "mangler", "FORKERT"):
    print(f"  {o:16} {outcomes[o]:4}  {outcomes[o] / n:6.1%}")
for o in ("FORKERT", "mangler", "usikker-forkert", "usikker-rigtig"):
    for d in details[o]:
        print(f"  [{o}] {d}")
