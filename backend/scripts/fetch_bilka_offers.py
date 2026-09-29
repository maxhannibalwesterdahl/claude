"""Gemmer ugens Bilka-tilbud fra madvareavisen som testdata.

    python scripts/fetch_bilka_offers.py > tests/data/bilka_offers_<dato>.json
"""

import json
import sys

from madplan.offers.tjek import fetch_food_offers

offers = fetch_food_offers()
print(f"{len(offers)} tilbud", file=sys.stderr)
json.dump([o.to_dict() for o in offers], sys.stdout, ensure_ascii=False, indent=1)
