import json
from datetime import datetime

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from madplan import push
from madplan.config import TZ
from madplan.models import MealReminder
from madplan.reminders import send_due, strip_husk

START = "2026-10-04"  # søndag; torsdag er 2026-10-08
ENDPOINT = "https://fcm.googleapis.com/fcm/send/abc"


@pytest.fixture
def plan(client):
    r = client.post("/api/recipes", json={"title": "Hakkebøf", "servings": 4,
                                          "ingredients": [{"raw": "500 g hakket oksekød"}]})
    plan = client.post("/api/plans", json={"start_date": START}).json()
    return client.put(f"/api/plans/{plan['id']}/slots",
                      json={"date": "2026-10-08", "kind": "opskrift", "recipe_id": r.json()["id"]}).json()


def thursday(plan):
    return next(d for d in plan["days"] if d["date"] == "2026-10-08")["meal"]


class Phone:
    """En telefon med sine egne nøgler, som kan læse de krypterede beskeder."""

    def __init__(self, endpoint=ENDPOINT):
        self.key = ec.generate_private_key(ec.SECP256R1())
        self.auth = b"0123456789abcdef"
        self.endpoint = endpoint
        self.got: list[dict] = []
        self.status = 201

    def keys(self):
        raw = self.key.public_key().public_bytes(serialization.Encoding.X962,
                                                 serialization.PublicFormat.UncompressedPoint)
        return {"p256dh": push.b64url(raw), "auth": push.b64url(self.auth)}

    def decrypt(self, body: bytes) -> dict:
        salt, idlen = body[:16], body[20]
        as_public = body[21:21 + idlen]
        sender = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), as_public)
        shared = self.key.exchange(ec.ECDH(), sender)
        ua_public = push.b64url_decode(self.keys()["p256dh"])
        prk_key = push._hmac(self.auth, shared)
        ikm = push._hmac(prk_key, b"WebPush: info\x00" + ua_public + as_public + b"\x01")
        prk = push._hmac(salt, ikm)
        cek = push._hmac(prk, b"Content-Encoding: aes128gcm\x00\x01")[:16]
        nonce = push._hmac(prk, b"Content-Encoding: nonce\x00\x01")[:12]
        plain = AESGCM(cek).decrypt(nonce, body[21 + idlen:], None)
        assert plain.endswith(b"\x02")
        return json.loads(plain[:-1])

    def post(self, url, content, headers, timeout):
        assert url == self.endpoint
        assert headers["Content-Encoding"] == "aes128gcm"
        assert headers["Authorization"].startswith("vapid t=")
        self.got.append(self.decrypt(content))
        return type("Res", (), {"status_code": self.status, "text": ""})()


def at(day, hour):
    return datetime(2026, 10, day, hour, 0, tzinfo=TZ)


def subscribe(client, phone):
    r = client.post("/api/push/subscriptions", json={"endpoint": phone.endpoint, "keys": phone.keys()},
                    headers={"Origin": "https://madplan.example.ts.net"})
    assert r.status_code == 204, r.text


def run(app, now, phone):
    return send_due(app.state.db.sessionmaker, app.state.settings.data_dir, now, post=phone.post)


def test_add_tick_and_remove(client, plan):
    meal = thursday(plan)
    p = client.post(f"/api/meals/{meal['id']}/reminders", json={"text": "  kød op af   fryseren "}).json()
    [r] = thursday(p)["reminders"]
    assert r["text"] == "kød op af fryseren" and r["done"] is False
    p = client.patch(f"/api/reminders/{r['id']}", json={"done": True}).json()
    assert thursday(p)["reminders"][0]["done"] is True
    p = client.delete(f"/api/reminders/{r['id']}").json()
    assert thursday(p)["reminders"] == []
    assert client.post(f"/api/meals/{meal['id']}/reminders", json={"text": " "}).status_code == 422


def test_reminder_follows_the_meal_when_moved(client, plan):
    meal = thursday(plan)
    client.post(f"/api/meals/{meal['id']}/reminders", json={"text": "kød op"})
    p = client.post(f"/api/meals/{meal['id']}/move", json={"date": "2026-10-09"}).json()
    friday = next(d for d in p["days"] if d["date"] == "2026-10-09")["meal"]
    assert [r["text"] for r in friday["reminders"]] == ["kød op"]


def test_sent_at_19_the_day_before_and_again_until_ticked(app, client, plan):
    meal = thursday(plan)
    client.post(f"/api/meals/{meal['id']}/reminders", json={"text": "Husk kød op af fryseren"})
    phone = Phone()
    subscribe(client, phone)

    assert run(app, at(7, 18), phone) == 0          # onsdag før kl. 19
    assert run(app, at(7, 19), phone) == 1          # onsdag kl. 19
    assert phone.got[-1]["title"] == "Husk: kød op af fryseren"
    assert phone.got[-1]["body"] == "Hakkebøf i morgen"
    assert phone.got[-1]["url"] == "/?dag=2026-10-08"
    assert run(app, at(7, 21), phone) == 0          # kun én gang pr. aften
    assert run(app, at(8, 19), phone) == 1          # ikke krydset af: igen torsdag
    assert phone.got[-1]["body"] == "Hakkebøf i dag"
    assert run(app, at(9, 19), phone) == 0          # retten er spist

    rid = thursday(client.get(f"/api/plans/{plan['id']}").json())["reminders"][0]["id"]
    with app.state.db.sessionmaker() as s:
        s.get(MealReminder, rid).sent_on = None
        s.commit()
    client.patch(f"/api/reminders/{rid}", json={"done": True})
    assert run(app, at(8, 20), phone) == 0          # krydset af: ingen besked


def test_waits_for_a_phone_and_drops_phones_that_are_gone(app, client, plan):
    meal = thursday(plan)
    client.post(f"/api/meals/{meal['id']}/reminders", json={"text": "kød op"})
    phone = Phone()
    assert run(app, at(7, 19), phone) == 0          # ingen telefoner endnu
    subscribe(client, phone)
    phone.status = 410
    assert run(app, at(7, 20), phone) == 0
    phone.status = 201
    assert run(app, at(7, 21), phone) == 0          # telefonen er slettet
    subscribe(client, phone)
    assert run(app, at(7, 22), phone) == 1


def test_unknown_push_service_is_refused(client):
    phone = Phone("https://evil.example.com/push")
    r = client.post("/api/push/subscriptions", json={"endpoint": phone.endpoint, "keys": phone.keys()})
    assert r.status_code == 422


def test_server_key_is_kept(client):
    a = client.get("/api/push/key").json()["public_key"]
    assert client.get("/api/push/key").json()["public_key"] == a
    assert len(push.b64url_decode(a)) == 65


@pytest.mark.parametrize("text, expected", [
    ("Husk kød op af fryseren", "kød op af fryseren"), ("husk at købe brød", "købe brød"),
    ("kød op", "kød op"), ("husk", "husk"),
])
def test_strip_husk(text, expected):
    assert strip_husk(text) == expected


def test_vapid_signature_verifies():
    key = ec.generate_private_key(ec.SECP256R1())
    header = push.vapid_header("https://web.push.apple.com/abc", key, "https://madplan.example")
    token = header.split("t=")[1].split(",")[0]
    head, body, sig = token.split(".")
    raw = push.b64url_decode(sig)
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature
    der = encode_dss_signature(int.from_bytes(raw[:32], "big"), int.from_bytes(raw[32:], "big"))
    key.public_key().verify(der, f"{head}.{body}".encode(), ec.ECDSA(hashes.SHA256()))
    claims = json.loads(push.b64url_decode(body))
    assert claims["aud"] == "https://web.push.apple.com" and claims["sub"] == "https://madplan.example"
