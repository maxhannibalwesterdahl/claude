"""Henter tilbud fra Tjek (tidligere eTilbudsavis).

Uofficielt API uden aftale (se docs/SPEC.md §6). Alt, der afhænger af Tjeks
format, ligger i dette modul, så det kan udskiftes, hvis API'et ændrer sig.
"""

import json
import re
import time
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass

BASE_URL = "https://squid-api.tjek.com/v2"
BILKA_DEALER_ID = "93f13"
PAGE_SIZE = 100
_UA = {"User-Agent": "madplan (privat brug)"}


@dataclass(frozen=True)
class Offer:
    id: str
    dealer: str
    heading: str
    description: str
    price: float
    pre_price: float | None
    # Mængde pr. stk, fx 500 g. "pieces" er antal i pakken (fx 24 dåser).
    size_from: float | None
    size_to: float | None
    unit: str | None
    pieces: int | None
    run_from: str
    run_till: str
    catalog_id: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def _get(path: str, params: dict) -> list[dict]:
    url = f"{BASE_URL}/{path}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _parse(raw: dict, dealer: str) -> Offer:
    q = raw.get("quantity") or {}
    size = q.get("size") or {}
    unit = (q.get("unit") or {}).get("symbol")
    pieces = (q.get("pieces") or {}).get("from")
    pricing = raw.get("pricing") or {}
    return Offer(
        id=raw["id"],
        dealer=dealer,
        heading=raw.get("heading", "").strip(),
        description=(raw.get("description") or "").strip(),
        price=pricing.get("price"),
        pre_price=pricing.get("pre_price"),
        size_from=size.get("from"),
        size_to=size.get("to"),
        unit=unit,
        pieces=pieces,
        run_from=raw.get("run_from", ""),
        run_till=raw.get("run_till", ""),
        catalog_id=raw.get("catalog_id") or "",
    )


# Tjek har ingen varekategorier. Bilka udgiver madvarer i en separat avis
# ("Bilka Food Uge 40 - Fødevarer & Personlig Pleje"), adskilt fra nonfood,
# halloween og elektronik. Kun den bruges, ellers bliver pyntegræskar til mad.
# Hele ord: "Bilka Nonfood" må ikke tælle som "food".
_FOOD_CATALOG_RE = re.compile(r"\b(?:food|fødevarer)\b", re.IGNORECASE)


def food_catalog_ids(dealer_id: str = BILKA_DEALER_ID) -> set[str]:
    catalogs = _get("catalogs", {"dealer_ids": dealer_id, "limit": 50})
    return {c["id"] for c in catalogs if _FOOD_CATALOG_RE.search(c.get("label") or "")}


def fetch_food_offers(dealer_id: str = BILKA_DEALER_ID, dealer: str = "Bilka") -> list[Offer]:
    """Kun tilbud fra kædens madvareavis."""
    food = food_catalog_ids(dealer_id)
    return [o for o in fetch_offers(dealer_id, dealer) if o.catalog_id in food]


def fetch_offers(dealer_id: str = BILKA_DEALER_ID, dealer: str = "Bilka") -> list[Offer]:
    """Alle aktuelle tilbud fra én kæde, med sideinddeling."""
    offers: list[Offer] = []
    offset = 0
    while True:
        page = _get("offers", {"dealer_ids": dealer_id, "limit": PAGE_SIZE, "offset": offset})
        offers += [_parse(o, dealer) for o in page]
        if len(page) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
        time.sleep(0.5)
    # Samme tilbud kan optræde på flere sider i avisen.
    unique = {o.id: o for o in offers}
    return list(unique.values())
