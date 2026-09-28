"""Fase 0.3-spike: indkøbsliste med login, der virker offline.

Formål er kun at afprøve drift (Proxmox + Tailscale Funnel), login på en
offentlig adresse og offline-afkrydsning på rigtige telefoner. Koden smides
væk, når den rigtige app bygges. Se docs/PLAN.md, fase 0.3.

Miljøvariabler:
  APP_PASSWORD  fælles kodeord (spike: ét login til begge telefoner)
  APP_SECRET    hemmelig nøgle til at signere session-cookien
  DB_PATH       SQLite-fil (standard: /data/spike.db)
"""

import hashlib
import hmac
import os
import sqlite3
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager, closing
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from pydantic import BaseModel

STATIC = Path(__file__).parent / "static"
SESSION_DAYS = 90
COOKIE = "madplan_session"
LOGIN_LIMIT = 5  # forsøg pr. minut pr. IP

SEED = [
    ("Frugt & grønt", "Løg (3 stk)"),
    ("Frugt & grønt", "Gulerødder (500 g)"),
    ("Frugt & grønt", "Citron (1 stk)"),
    ("Kød & fisk", "Hakket oksekød (800 g)"),
    ("Kød & fisk", "Laksefilet (600 g)"),
    ("Mejeri & køl", "Piskefløde (2½ dl)"),
    ("Mejeri & køl", "Frisk mozzarella (250 g)"),
    ("Kolonial", "Hakkede tomater (2 dåser)"),
    ("Kolonial", "Lasagneplader (200 g)"),
    ("Andet", "Bleer"),
]

@asynccontextmanager
async def _lifespan(_app):
    init_db()
    yield


app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=_lifespan)
_attempts: dict[str, deque] = defaultdict(deque)


def _db_path() -> str:
    return os.environ.get("DB_PATH", "/data/spike.db")


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    Path(_db_path()).parent.mkdir(parents=True, exist_ok=True)
    with closing(_conn()) as c, c:
        c.execute(
            "CREATE TABLE IF NOT EXISTS item ("
            " id INTEGER PRIMARY KEY, department TEXT, name TEXT,"
            " checked INTEGER DEFAULT 0, updated_ms INTEGER DEFAULT 0)"
        )
        if c.execute("SELECT COUNT(*) FROM item").fetchone()[0] == 0:
            c.executemany("INSERT INTO item (department, name) VALUES (?, ?)", SEED)


# --- Login -----------------------------------------------------------------

def _secret() -> bytes:
    secret = os.environ.get("APP_SECRET", "")
    if len(secret) < 32:
        raise RuntimeError("APP_SECRET skal være mindst 32 tegn")
    return secret.encode()


def make_session(now: float | None = None) -> str:
    expires = int((now or time.time()) + SESSION_DAYS * 86400)
    sig = hmac.new(_secret(), str(expires).encode(), hashlib.sha256).hexdigest()
    return f"{expires}.{sig}"


def valid_session(value: str | None, now: float | None = None) -> bool:
    if not value or "." not in value:
        return False
    expires, sig = value.split(".", 1)
    expected = hmac.new(_secret(), expires.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(sig, expected) and expires.isdigit() and int(expires) > (now or time.time())


def _client_ip(request: Request) -> str:
    # Tailscale Funnel sender den rigtige klient-IP i X-Forwarded-For.
    fwd = request.headers.get("x-forwarded-for", "")
    return fwd.split(",")[0].strip() or (request.client.host if request.client else "?")


def _rate_limited(ip: str) -> bool:
    q = _attempts[ip]
    now = time.monotonic()
    while q and now - q[0] > 60:
        q.popleft()
    q.append(now)
    return len(q) > LOGIN_LIMIT


def require_login(request: Request) -> None:
    if not valid_session(request.cookies.get(COOKIE)):
        raise HTTPException(status_code=401, detail="Ikke logget ind")


@app.get("/login", response_class=HTMLResponse)
def login_page(error: str = "") -> str:
    msg = f'<p class="err">{error}</p>' if error else ""
    return (STATIC / "login.html").read_text("utf-8").replace("<!--ERR-->", msg)


@app.post("/login")
def login(request: Request, password: str = Form(...)):
    if _rate_limited(_client_ip(request)):
        return RedirectResponse("/login?error=For+mange+forsøg.+Vent+et+minut.", status_code=303)
    expected = os.environ.get("APP_PASSWORD", "")
    if not expected or not hmac.compare_digest(password.encode(), expected.encode()):
        return RedirectResponse("/login?error=Forkert+kodeord", status_code=303)
    resp = RedirectResponse("/", status_code=303)
    resp.set_cookie(
        COOKIE, make_session(), max_age=SESSION_DAYS * 86400,
        httponly=True, secure=request.url.scheme == "https" or "x-forwarded-for" in request.headers,
        samesite="lax",
    )
    return resp


# --- Indkøbsliste ----------------------------------------------------------

class Change(BaseModel):
    id: int
    checked: bool
    ts: int  # klientens tidspunkt i ms, da ændringen blev lavet


class SyncRequest(BaseModel):
    changes: list[Change] = []


def _all_items(c: sqlite3.Connection) -> list[dict]:
    rows = c.execute("SELECT id, department, name, checked, updated_ms FROM item ORDER BY id")
    return [dict(r) | {"checked": bool(r["checked"])} for r in rows]


@app.post("/api/sync")
def sync(body: SyncRequest, request: Request) -> dict:
    """Modtag ændringer lavet offline. Seneste ændring pr. vare vinder."""
    require_login(request)
    with closing(_conn()) as c, c:
        for ch in body.changes:
            c.execute(
                "UPDATE item SET checked = ?, updated_ms = ? WHERE id = ? AND updated_ms < ?",
                (int(ch.checked), ch.ts, ch.id, ch.ts),
            )
        return {"items": _all_items(c), "server_ms": int(time.time() * 1000)}


@app.post("/api/reset")
def reset(request: Request) -> dict:
    """Fjern alle flueben (til at gentage testen)."""
    require_login(request)
    now = int(time.time() * 1000)
    with closing(_conn()) as c, c:
        c.execute("UPDATE item SET checked = 0, updated_ms = ?", (now,))
        return {"items": _all_items(c), "server_ms": now}


# --- Statiske filer (app-skal, må caches offline) ---------------------------

@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-cache"})


@app.get("/sw.js")
def service_worker() -> FileResponse:
    return FileResponse(STATIC / "sw.js", media_type="text/javascript", headers={"Cache-Control": "no-cache"})


@app.get("/{name}")
def static_file(name: str) -> FileResponse:
    allowed = {"app.js", "style.css", "manifest.webmanifest", "icon.svg"}
    if name not in allowed:
        raise HTTPException(status_code=404)
    return FileResponse(STATIC / name, headers={"Cache-Control": "no-cache"})
