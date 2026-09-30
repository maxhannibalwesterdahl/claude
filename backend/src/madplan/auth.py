"""Login: argon2-kodeord, signeret session-cookie og begrænsning af forsøg.

Adressen er offentlig via Tailscale Funnel, så loginforsøg begrænses pr. IP.
Cookien indeholder bruger-id, sessionsversion og udløb, signeret med
APP_SECRET. Nyt kodeord øger sessionsversionen og logger alle enheder ud.
"""

import hashlib
import hmac
import threading
import time
from collections import defaultdict, deque

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

COOKIE = "madplan_session"
SESSION_DAYS = 90
LOGIN_LIMIT = 5  # forsøg pr. minut pr. IP
MIN_PASSWORD = 12

_hasher = PasswordHasher()
# Hvert tjek af et kodeord bruger 64 MB RAM (argon2). Højst to ad gangen, så en
# flod af loginforsøg ikke kan fylde containerens hukommelse.
HASH_GATE = threading.BoundedSemaphore(2)
# Bruges, når brugernavnet ikke findes, så svartiden ikke afslører det.
_DUMMY_HASH = _hasher.hash("ikke-et-rigtigt-kodeord")


def hash_password(password: str) -> str:
    if len(password) < MIN_PASSWORD:
        raise ValueError(f"Kodeordet skal være mindst {MIN_PASSWORD} tegn")
    return _hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerificationError, InvalidHashError):
        return False


def _sign(secret: str, payload: str) -> str:
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


def make_session(secret: str, user_id: int, version: int, now: float | None = None) -> str:
    expires = int((now or time.time()) + SESSION_DAYS * 86400)
    payload = f"{user_id}.{version}.{expires}"
    return f"{payload}.{_sign(secret, payload)}"


def read_session(secret: str, value: str | None, now: float | None = None) -> tuple[int, int] | None:
    """(bruger-id, sessionsversion) for en gyldig cookie, ellers None."""
    if not value:
        return None
    parts = value.split(".")
    if len(parts) != 4 or not all(p.isdigit() for p in parts[:3]):
        return None
    payload = ".".join(parts[:3])
    if not hmac.compare_digest(parts[3], _sign(secret, payload)):
        return None
    user_id, version, expires = (int(p) for p in parts[:3])
    if expires <= (now or time.time()):
        return None
    return user_id, version


class RateLimiter:
    def __init__(self, limit: int = LOGIN_LIMIT, window: float = 60.0):
        self.limit = limit
        self.window = window
        self._attempts: dict[str, deque[float]] = defaultdict(deque)

    def _recent(self, key: str, now: float) -> deque[float]:
        q = self._attempts[key]
        while q and now - q[0] > self.window:
            q.popleft()
        return q

    def blocked(self, key: str, now: float | None = None) -> bool:
        """True, hvis der har været for mange mislykkede forsøg for nylig."""
        now = time.monotonic() if now is None else now
        return len(self._recent(key, now)) >= self.limit

    def failed(self, key: str, now: float | None = None) -> None:
        now = time.monotonic() if now is None else now
        self._recent(key, now).append(now)

    def succeeded(self, key: str) -> None:
        """Fjern det seneste forsøg igen (det blev talt, før kodeordet var tjekket)."""
        q = self._attempts.get(key)
        if q:
            q.pop()
        if not q:
            self._attempts.pop(key, None)
