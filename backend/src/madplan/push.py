"""Web Push: beskeder til telefoner, der har sagt ja (RFC 8291 og 8292).

Serverens nøgle (VAPID) laves første gang og gemmes i datamappen. Den skal
blive liggende: telefonerne er tilmeldt med den, og en ny nøgle betyder, at de
skal sige ja igen (det gør appen selv, næste gang den åbnes).
"""

import base64
import json
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import httpx
from cryptography.hazmat.primitives import hashes, hmac, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

log = logging.getLogger("madplan")

# Kun de kendte push-tjenester (Apple, Google, Mozilla, Microsoft). Serveren
# sender ikke til vilkårlige adresser, en klient har opgivet.
PUSH_HOSTS = ("push.apple.com", "googleapis.com", "push.services.mozilla.com", "notify.windows.com")

RECORD_SIZE = 4096


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def b64url_decode(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def allowed_endpoint(endpoint: str) -> bool:
    u = urlparse(endpoint)
    host = (u.hostname or "").lower()
    return u.scheme == "https" and any(host == h or host.endswith("." + h) for h in PUSH_HOSTS)


def load_key(data_dir: Path) -> ec.EllipticCurvePrivateKey:
    """Serverens VAPID-nøgle. Laves første gang."""
    path = data_dir / "vapid.pem"
    if path.is_file():
        key = serialization.load_pem_private_key(path.read_bytes(), password=None)
        assert isinstance(key, ec.EllipticCurvePrivateKey)
        return key
    key = ec.generate_private_key(ec.SECP256R1())
    data_dir.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_bytes(key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ))
    os.replace(tmp, path)
    return key


def public_key(key: ec.EllipticCurvePrivateKey) -> str:
    """Den offentlige nøgle, som telefonen tilmelder sig med (applicationServerKey)."""
    raw = key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    return b64url(raw)


def _hmac(key: bytes, data: bytes) -> bytes:
    h = hmac.HMAC(key, hashes.SHA256())
    h.update(data)
    return h.finalize()


def encrypt(payload: bytes, p256dh: str, auth: str, *, salt: bytes | None = None,
            sender: ec.EllipticCurvePrivateKey | None = None) -> bytes:
    """Krypterer beskeden til én telefon (aes128gcm, RFC 8291)."""
    ua_public = b64url_decode(p256dh)
    auth_secret = b64url_decode(auth)
    salt = salt or os.urandom(16)
    sender = sender or ec.generate_private_key(ec.SECP256R1())
    as_public = sender.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    ua_key = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), ua_public)
    shared = sender.exchange(ec.ECDH(), ua_key)

    prk_key = _hmac(auth_secret, shared)
    ikm = _hmac(prk_key, b"WebPush: info\x00" + ua_public + as_public + b"\x01")
    prk = _hmac(salt, ikm)
    cek = _hmac(prk, b"Content-Encoding: aes128gcm\x00\x01")[:16]
    nonce = _hmac(prk, b"Content-Encoding: nonce\x00\x01")[:12]

    # Én post: beskeden og afgrænseren 0x02 (sidste post).
    body = AESGCM(cek).encrypt(nonce, payload + b"\x02", None)
    header = salt + RECORD_SIZE.to_bytes(4, "big") + bytes([len(as_public)]) + as_public
    return header + body


def vapid_header(endpoint: str, key: ec.EllipticCurvePrivateKey, subject: str) -> str:
    """Authorization-feltet: en underskrevet JWT (ES256) til push-tjenesten."""
    u = urlparse(endpoint)
    claims = {"aud": f"{u.scheme}://{u.netloc}", "exp": int(time.time()) + 12 * 3600, "sub": subject}
    head = b64url(json.dumps({"typ": "JWT", "alg": "ES256"}, separators=(",", ":")).encode())
    body = b64url(json.dumps(claims, separators=(",", ":")).encode())
    signing_input = f"{head}.{body}".encode()
    r, s = decode_dss_signature(key.sign(signing_input, ec.ECDSA(hashes.SHA256())))
    sig = b64url(r.to_bytes(32, "big") + s.to_bytes(32, "big"))
    return f"vapid t={head}.{body}.{sig}, k={public_key(key)}"


@dataclass(frozen=True)
class Target:
    endpoint: str
    p256dh: str
    auth: str


# Svar fra push-tjenesten: telefonen har meldt fra eller er slettet.
GONE = {404, 410}


def send(target: Target, message: dict, key: ec.EllipticCurvePrivateKey, subject: str,
         post=httpx.post) -> int:
    """Sender én besked. Svarer med HTTP-status (0, hvis den ikke kunne nås)."""
    data = encrypt(json.dumps(message, ensure_ascii=False).encode(), target.p256dh, target.auth)
    headers = {
        "Authorization": vapid_header(target.endpoint, key, subject),
        "Content-Encoding": "aes128gcm",
        "Content-Type": "application/octet-stream",
        # En påmindelse er ikke værd at få dagen efter.
        "TTL": str(12 * 3600),
        "Urgency": "high",
    }
    try:
        res = post(target.endpoint, content=data, headers=headers, timeout=15)
    except httpx.HTTPError as e:
        log.warning("besked kunne ikke sendes til %s: %s", urlparse(target.endpoint).hostname, e)
        return 0
    if res.status_code >= 300 and res.status_code not in GONE:
        log.warning("push-tjenesten svarede %s: %s", res.status_code, res.text[:200])
    return res.status_code
