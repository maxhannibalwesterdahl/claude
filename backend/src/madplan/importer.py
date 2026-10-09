"""Import af opskrifter fra et link med recipe-scrapers.

Virker for sider med egen læser i recipe-scrapers (Valdemarsro, Madens Verden,
DR, ...) og for sider med generiske schema.org/Recipe-data (fx Arla).
nemlig.com læses fra sidens egne JSON-data, fordi kun de har mængderne med.
"""

import ipaddress
import json
import re
import socket
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from recipe_scrapers import scrape_html

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0 Safari/537.36",
    "Accept-Language": "da,en;q=0.8",
}
# nemlig.com sender browsere i kø (Queue-it), men lader andre klienter hente
# siderne direkte. Vi siger derfor ærligt, hvem vi er.
NEMLIG_HEADERS = {"User-Agent": "madplan/1.0 (privat madplan; opskriftsimport)", "Accept-Language": "da"}
MAX_PAGE = 5_000_000
MAX_IMAGE = 8_000_000
IMAGE_TYPES = {"image/jpeg": ".jpg", "image/jpg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/avif": ".avif"}


class RecipeImportError(Exception):
    """Fejl, der vises for brugeren."""


@dataclass
class ScrapedGroup:
    name: str
    lines: list[str]


@dataclass
class ScrapedRecipe:
    title: str
    servings: int | None
    groups: list[ScrapedGroup]
    instructions: list[str]
    image_url: str | None
    source_url: str
    warnings: list[str] = field(default_factory=list)


def check_url(url: str) -> str:
    """Kun offentlige http(s)-adresser, så importen ikke kan bruges til at nå
    maskiner på hjemmenettet."""
    url = url.strip()
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise RecipeImportError("Linket skal starte med https://")
    try:
        infos = socket.getaddrinfo(parsed.hostname, parsed.port or 443, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        raise RecipeImportError(f"Kan ikke finde siden {parsed.hostname}") from None
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global:
            raise RecipeImportError("Linket peger på en lokal adresse")
    return url


@dataclass
class _Fetched:
    body: bytes
    content_type: str
    charset: str | None


def _get(client: httpx.Client, url: str, limit: int) -> _Fetched:
    """Hent med grænse på størrelse og tjek af hver omdirigering."""
    for _ in range(5):
        check_url(url)
        with client.stream("GET", url) as r:
            if r.is_redirect:
                url = str(r.url.join(r.headers["location"]))
                continue
            r.raise_for_status()
            body = bytearray()
            for chunk in r.iter_bytes():
                body += chunk
                if len(body) > limit:
                    raise RecipeImportError("Siden er for stor")
            content_type = r.headers.get("content-type", "").split(";")[0].strip().lower()
            return _Fetched(bytes(body), content_type, r.charset_encoding)
    raise RecipeImportError("For mange omdirigeringer")


def fetch(url: str, client: httpx.Client | None = None, headers: dict[str, str] = HEADERS) -> str:
    own = client is None
    client = client or httpx.Client(headers=headers, timeout=15, follow_redirects=False)
    try:
        page = _get(client, url, MAX_PAGE)
        return page.body.decode(page.charset or "utf-8", errors="replace")
    except httpx.HTTPStatusError as e:
        raise RecipeImportError(f"Siden svarede med fejl {e.response.status_code}") from None
    except httpx.HTTPError:
        raise RecipeImportError("Kunne ikke hente siden") from None
    finally:
        if own:
            client.close()


def _servings(text: str | None) -> int | None:
    m = re.search(r"\d+", text or "")
    return int(m.group()) if m else None


def _safe(fn, default):
    try:
        value = fn()
    except Exception:  # recipe-scrapers kaster mange slags fejl for manglende felter
        return default
    return value if value else default


def scrape(html: str, url: str) -> ScrapedRecipe:
    try:
        s = scrape_html(html, org_url=url, supported_only=False)
    except Exception:
        raise RecipeImportError("Siden har ingen opskriftsdata, som kan læses") from None

    title = _safe(s.title, "").strip()
    lines = [x.strip() for x in _safe(s.ingredients, []) if x and x.strip()]
    if not title or not lines:
        raise RecipeImportError("Siden har ingen opskrift med ingredienser")

    groups = []
    for g in _safe(s.ingredient_groups, []):
        g_lines = [x.strip() for x in g.ingredients if x and x.strip()]
        if g_lines:
            groups.append(ScrapedGroup((g.purpose or "").strip(), g_lines))
    if sum(len(g.lines) for g in groups) != len(lines):
        groups = [ScrapedGroup("", lines)]

    instructions = [x.strip() for x in _safe(s.instructions_list, []) if x and x.strip()]
    warnings = [] if instructions else ["Fremgangsmåden kunne ikke læses"]
    return ScrapedRecipe(
        title=title,
        servings=_servings(str(_safe(s.yields, ""))),
        groups=groups,
        instructions=instructions,
        image_url=_safe(s.image, None),
        source_url=url,
        warnings=warnings,
    )


def is_nemlig(url: str) -> bool:
    return (urlparse(url).hostname or "").lower() in ("nemlig.com", "www.nemlig.com")


def _nemlig_line(ing: dict) -> str:
    """Saml nemligs adskilte mængde, enhed og navn til en linje: "2 stk. løg"."""
    text = " ".join((ing.get("Text") or "").split())
    amount = (ing.get("Amount") or "").strip().replace(".", ",")
    if not text or amount in ("", "0"):
        return text
    unit = (ing.get("Unit") or "").strip()
    return " ".join(x for x in (amount, unit, text[0].lower() + text[1:]) if x)


def scrape_nemlig(page: str, url: str) -> ScrapedRecipe:
    """Læs en opskrift fra nemlig.coms sidedata (`?GetAsJson=1`)."""
    try:
        spots = json.loads(page)["content"]
        spot = next(c for c in spots if c.get("TemplateName") == "recipedetailspot")
    except (ValueError, KeyError, TypeError, AttributeError, StopIteration):
        raise RecipeImportError("Siden har ingen opskriftsdata, som kan læses") from None

    title = (spot.get("Header") or "").strip()
    groups = []
    for g in spot.get("IngredientGroups") or []:
        lines = [l for l in map(_nemlig_line, g.get("Ingredients") or []) if l]
        if lines:
            groups.append(ScrapedGroup((g.get("Name") or "").strip(), lines))
    if not title or not groups:
        raise RecipeImportError("Siden har ingen opskrift med ingredienser")
    if len(groups) == 1:
        groups[0].name = ""

    # Trinene står som punkter; tips og mellemrubrikker udenom tages ikke med.
    soup = BeautifulSoup(spot.get("Instructions") or "", "html.parser")
    steps = [x.get_text(" ", strip=True) for x in soup.find_all("li")] or [x.get_text(" ", strip=True) for x in soup.find_all("p")]
    instructions = [" ".join(x.split()) for x in steps if x.strip()]

    image = next((m.get("Url") for m in spot.get("Media") or [] if m.get("MediaType") == "image" and m.get("Url")), None)
    persons = spot.get("NumberOfPersons")
    return ScrapedRecipe(
        title=title,
        servings=persons if isinstance(persons, int) and persons > 0 else None,
        groups=groups,
        instructions=instructions,
        # Originalen er ofte flere MB; 1200 px er rigeligt.
        image_url=f"{image}&w=1200" if image and "?" in image else image,
        source_url=url,
        warnings=[] if instructions else ["Fremgangsmåden kunne ikke læses"],
    )


def load(url: str) -> ScrapedRecipe:
    """Hent og læs opskriften bag et link."""
    if is_nemlig(url):
        return scrape_nemlig(fetch(url.split("?")[0].split("#")[0] + "?GetAsJson=1", headers=NEMLIG_HEADERS), url)
    return scrape(fetch(url), url)


def download_image(url: str, image_dir: Path, client: httpx.Client | None = None) -> str | None:
    """Gem billedet lokalt. Returnerer filnavnet, eller None hvis det ikke lykkes."""
    own = client is None
    client = client or httpx.Client(headers=HEADERS, timeout=15, follow_redirects=False)
    try:
        image = _get(client, url, MAX_IMAGE)
        ext = IMAGE_TYPES.get(image.content_type)
        if not ext:
            return None
        image_dir.mkdir(parents=True, exist_ok=True)
        name = uuid.uuid4().hex + ext
        (image_dir / name).write_bytes(image.body)
        return name
    except (httpx.HTTPError, RecipeImportError):
        return None
    finally:
        if own:
            client.close()
