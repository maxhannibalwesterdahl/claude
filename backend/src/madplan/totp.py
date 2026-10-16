"""Tofaktor: TOTP efter RFC 6238 (SHA-1, 6 cifre, 30 sekunder) uden ekstra afhængigheder.

Hemmeligheden gemmes krypteret med en nøgle afledt af APP_SECRET.
"""

import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote

from cryptography.fernet import Fernet, InvalidToken

STEP = 30
DIGITS = 6
WINDOW = 1  # accepterer også forrige og næste kode (urforskel)


def new_secret() -> str:
    """Base32, som authenticator-apps forventer."""
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def _key(app_secret: str) -> bytes:
    return base64.urlsafe_b64encode(hashlib.sha256(("totp:" + app_secret).encode()).digest())


def seal(app_secret: str, secret: str) -> str:
    return Fernet(_key(app_secret)).encrypt(secret.encode()).decode()


def unseal(app_secret: str, sealed: str) -> str | None:
    try:
        return Fernet(_key(app_secret)).decrypt(sealed.encode()).decode()
    except InvalidToken:
        return None


def code_at(secret: str, step: int) -> str:
    key = base64.b32decode(secret + "=" * (-len(secret) % 8))
    digest = hmac.new(key, struct.pack(">Q", step), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = (struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF) % 10**DIGITS
    return str(value).zfill(DIGITS)


def verify(secret: str, code: str, last_step: int = 0, now: float | None = None) -> int | None:
    """Trinnet (tidsvindue), koden passer til, ellers None. Et trin, der allerede er
    brugt (`last_step`), afvises, så en aflyttet kode ikke kan bruges igen."""
    code = code.strip().replace(" ", "")
    if not (code.isdigit() and len(code) == DIGITS):
        return None
    current = int((now if now is not None else time.time()) // STEP)
    for step in range(current - WINDOW, current + WINDOW + 1):
        if step > last_step and hmac.compare_digest(code_at(secret, step), code):
            return step
    return None


def uri(secret: str, account: str, issuer: str = "Madplan admin") -> str:
    return f"otpauth://totp/{quote(issuer)}:{quote(account)}?secret={secret}&issuer={quote(issuer)}&digits={DIGITS}&period={STEP}"
