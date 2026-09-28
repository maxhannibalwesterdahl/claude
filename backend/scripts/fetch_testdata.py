"""Henter ingredienslinjer fra et tilfældigt, fast udvalg af opskrifter.

Bruges kun til at lave testdata til den danske ingredienslæser. Kører langsomt
med vilje (1 sekund mellem kald) for ikke at belaste siderne.

    python scripts/fetch_testdata.py valdemarsro 30 > tests/data/valdemarsro_raw.json
    python scripts/fetch_testdata.py madensverden 15 > tests/data/holdout_madensverden.json
"""

import json
import random
import re
import sys
import time
import urllib.request

from recipe_scrapers import scrape_html

SITES = {
    "valdemarsro": {
        "sitemaps": [f"https://www.valdemarsro.dk/post-sitemap{n}.xml" for n in ("", "2", "3")],
        "keep": lambda u: u.count("/") == 4,
    },
    "madensverden": {
        "sitemaps": [f"https://madensverden.dk/post-sitemap{n}.xml" for n in ("", "2", "3", "4", "5")],
        "keep": lambda u: u.count("/") == 4,
    },
    "arla": {
        "sitemaps": ["https://www.arla.dk/sitemap.xml?type=Modules.Recipes.Business.SitemapUrlWriter.RecipeSitemapUrlWriter"],
        "keep": lambda u: "/opskrifter/" in u,
    },
    # Spis Bedre har ingen strukturerede opskriftsdata i HTML'en (0/204 testet
    # 28-09-2026), så import derfra virker ikke. Beholdt for at kunne gentjekke.
    "spisbedre": {
        "sitemaps": ["https://spisbedre.dk/opskrifter/sitemap.xml"]
        + [f"https://spisbedre.dk/opskrifter/sitemap.xml?page={n}" for n in (2, 3, 4)],
        "keep": lambda u: "/opskrifter/" in u and not u.endswith(".xml"),
    },
}
UA = {"User-Agent": "Mozilla/5.0 (madplan testdata)"}
SEED = int(sys.argv[3]) if len(sys.argv) > 3 else 20260928


def get(url: str) -> str:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8")


def main(site: str, target: int) -> None:
    cfg = SITES[site]
    urls: list[str] = []
    for sm in cfg["sitemaps"]:
        try:
            urls += re.findall(r"<loc>([^<]+)</loc>", get(sm))
        except Exception as exc:
            print(f"sitemap fejl {sm}: {exc}", file=sys.stderr)
        time.sleep(1)
    urls = sorted(set(u for u in urls if cfg["keep"](u)))
    random.Random(SEED).shuffle(urls)

    recipes = []
    for url in urls:
        if len(recipes) >= target:
            break
        time.sleep(1)
        try:
            s = scrape_html(get(url), org_url=url, supported_only=False)
            ingredients = s.ingredients()
            title = s.title()
        except Exception as exc:  # artikler uden opskrift, 404 osv.
            print(f"skip {url}: {type(exc).__name__}", file=sys.stderr)
            continue
        if not ingredients:
            print(f"skip {url}: ingen ingredienser", file=sys.stderr)
            continue
        recipes.append({"url": url, "title": title, "ingredients": ingredients})
        print(f"ok   {url} ({len(ingredients)})", file=sys.stderr)

    json.dump(recipes, sys.stdout, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]))
