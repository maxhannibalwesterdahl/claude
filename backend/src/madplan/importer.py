"""Import af opskrifter fra et link med recipe-scrapers.

Virker for sider med egen læser i recipe-scrapers (Valdemarsro, Madens Verden,
DR, ...) og for sider med generiske schema.org/Recipe-data (fx Arla).
"""

import ipaddress
import re
import socket
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

import httpx
from recipe_scrapers import scrape_html

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0 Safari/537.36",
    "Accept-Language": "da,en;q=0.8",
}
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


def fetch(url: str, client: httpx.Client | None = None) -> str:
    own = client is None
    client = client or httpx.Client(headers=HEADERS, timeout=15, follow_redirects=False)
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
