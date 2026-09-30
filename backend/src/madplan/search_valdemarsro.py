"""Søgning på valdemarsro.dk (SPEC §3.1 og fase 5).

Bruger sidens egen søgning (`/?s=`), der ikke er et officielt API og kan ændre
sig. Isoleret her, så appen virker uden: fejler søgningen, vises kun jeres egne
opskrifter. Resultaterne gemmes i 10 minutter for ikke at belaste siden.

Søgningen returnerer også artikler ("16 frysevenlige opskrifter", "Små glimt").
De mest oplagte sorteres fra her; resten opdages ved import (ingen opskriftsdata).
"""

import html
import re
import time
from dataclasses import dataclass

import httpx

from .importer import HEADERS

BASE = "https://www.valdemarsro.dk/"
CACHE_SECONDS = 600
MAX_RESULTS = 24

_ITEM_RE = re.compile(
    r'<div class="post-list-item"[^>]*>.*?data-src="(?P<img>[^"]*)".*?'
    r'post-list-item-title[^>]*><a href="(?P<url>[^"]*)">(?P<title>[^<]*)</a>',
    re.S,
)
# Artikler og lister, ikke opskrifter: "16 skønne ...", "Små glimt", "Ses vi ...?"
_ARTICLE_RE = re.compile(r"^\d+\s|^små glimt|\?$", re.I)

_cache: dict[str, tuple[float, list["Hit"]]] = {}


@dataclass(frozen=True)
class Hit:
    title: str
    url: str
    image_url: str


class SearchError(Exception):
    pass


def parse(page: str) -> list[Hit]:
    hits, seen = [], set()
    for m in _ITEM_RE.finditer(page):
        url = m["url"].strip()
        title = html.unescape(m["title"]).strip()
        if not url.startswith(BASE) or url in seen or not title or _ARTICLE_RE.search(title):
            continue
        seen.add(url)
        hits.append(Hit(title=title, url=url, image_url=m["img"].strip()))
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
    client = client or httpx.Client(headers=HEADERS, timeout=15, follow_redirects=True)
    try:
        r = client.get(BASE, params={"s": key})
        r.raise_for_status()
    except httpx.HTTPError:
        raise SearchError("Valdemarsro svarer ikke lige nu") from None
    finally:
        if own:
            client.close()
    hits = parse(r.text)
    if len(_cache) > 200:
        _cache.clear()
    _cache[key] = (now, hits)
    return hits
