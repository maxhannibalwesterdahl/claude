"""Søgning i opskrifterne på nemlig.com (kun opskrifter, ikke varer).

Bruger sidens egen søgning (`/webapi/.../Search/Search`), der ikke er et
officielt API og kan ændre sig. Isoleret her ligesom Valdemarsro-søgningen:
fejler den, vises bare ingen resultater herfra. Resultaterne gemmes i 10 minutter.

`take=0` beder om ingen varer; `recipeCount` er antallet af opskrifter.
"""

import time

import httpx

from .importer import NEMLIG_HEADERS
from .search_valdemarsro import CACHE_SECONDS, MAX_RESULTS, Hit, SearchError

BASE = "https://www.nemlig.com"
# De to første led er sidens cache-nøgler (tidsstempel og leveringstid); de er
# ligegyldige for opskrifter.
SEARCH_URL = BASE + "/webapi/s/0/1/0/Search/Search"
THUMB = "&w=120&h=120&mode=crop"

_cache: dict[str, tuple[float, list[Hit]]] = {}


def parse(data: dict) -> list[Hit]:
    hits, seen = [], set()
    for r in data.get("Recipes") or []:
        path = (r.get("Url") or "").strip()
        title = (r.get("Name") or "").strip()
        if not path.startswith("/opskrifter/") or path in seen or not title:
            continue
        seen.add(path)
        image = (r.get("PrimaryImage") or "").strip()
        hits.append(Hit(title=title, url=BASE + path, image_url=image + THUMB if "?" in image else image))
        if len(hits) == MAX_RESULTS:
            break
    return hits


def search(q: str, client: httpx.Client | None = None) -> list[Hit]:
    key = " ".join(q.lower().split())
    now = time.monotonic()
    cached = _cache.get(key)
    if cached and now - cached[0] < CACHE_SECONDS:
        return cached[1]
    own = client is None
    client = client or httpx.Client(headers=NEMLIG_HEADERS, timeout=15, follow_redirects=True)
    try:
        r = client.get(SEARCH_URL, params={"query": key, "take": 0, "recipeCount": MAX_RESULTS})
        r.raise_for_status()
        data = r.json()
    except (httpx.HTTPError, ValueError):
        raise SearchError("nemlig.com svarer ikke lige nu") from None
    finally:
        if own:
            client.close()
    hits = parse(data if isinstance(data, dict) else {})
    if len(_cache) > 200:
        _cache.clear()
    _cache[key] = (now, hits)
    return hits
