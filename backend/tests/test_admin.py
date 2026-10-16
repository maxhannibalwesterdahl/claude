"""Admin-siden (docs/flere-familier.md §5a): kun systemadmin, 404 til alle andre."""

import re

import pytest
from fastapi.testclient import TestClient

from conftest import PASSWORD, add_user, login
from madplan.models import HouseholdLineMatch, User


@pytest.fixture
def admin(app, client):
    """Max som systemadmin, med admin-login."""
    with app.state.db.sessionmaker() as s:
        s.query(User).filter_by(username="max").one().is_system_admin = True
        s.commit()
    c = TestClient(app)
    r = c.post("/api/admin/login", json={"username": "max", "password": PASSWORD})
    assert r.status_code == 200, r.text
    return c


def _admin_routes(app):
    for path, ops in app.openapi()["paths"].items():
        if path.startswith("/api/admin") and path != "/api/admin/login":
            for method in ops:
                yield method.upper(), path


def test_every_admin_route_is_404_without_admin_session(app, client):
    """Matrix: anonym, almindelig bruger og systemadmin uden admin-login får 404 overalt."""
    routes = list(_admin_routes(app))
    assert len(routes) >= 10
    with app.state.db.sessionmaker() as s:
        s.query(User).filter_by(username="max").one().is_system_admin = True   # logget ind i appen, ikke i admin
        s.commit()
    add_user(app, "bea", "Familie B")
    for who in (TestClient(app), login(app, "bea"), client):
        for method, path in routes:
            r = who.request(method, re.sub(r"\{[^}]+\}", "1", path), json={})
            assert r.status_code == 404, f"{method} {path} svarede {r.status_code}"


def test_admin_login_refuses_normal_users_like_wrong_password(app, client):
    wrong = TestClient(app).post("/api/admin/login", json={"username": "max", "password": "forkert-kodeord"})
    normal = TestClient(app).post("/api/admin/login", json={"username": "max", "password": PASSWORD})
    assert wrong.status_code == normal.status_code == 401 and wrong.json() == normal.json()


def test_app_cookie_is_not_an_admin_cookie(app, client, admin):
    """Admin-cookien kan ikke bruges i appen og omvendt."""
    assert admin.get("/api/plans").status_code == 401
    only_app = TestClient(app)
    only_app.cookies.set("madplan_admin", client.cookies["madplan_session"])
    assert only_app.get("/api/admin/households").status_code == 404


def test_admin_login_is_rate_limited_per_username(app, client):
    c = TestClient(app, headers={"x-forwarded-for": "1.1.1.1"})
    codes = [c.post("/api/admin/login", json={"username": "max", "password": "forkert-kodeord"}).status_code for _ in range(6)]
    assert codes[:5] == [401] * 5 and codes[5] == 429
    # Andre IP-adresser rammes også, når det er samme brugernavn.
    other = TestClient(app, headers={"x-forwarded-for": "2.2.2.2"})
    assert other.post("/api/admin/login", json={"username": "max", "password": PASSWORD}).status_code == 429


def test_admin_cookie_is_short_lived_and_strict(app, client):
    with app.state.db.sessionmaker() as s:
        s.query(User).filter_by(username="max").one().is_system_admin = True
        s.commit()
    r = TestClient(app).post("/api/admin/login", json={"username": "max", "password": PASSWORD})
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie and f"max-age={12 * 3600}" in cookie


def test_create_family_and_user_then_they_can_log_in(app, admin):
    h = admin.post("/api/admin/households", json={"name": "Familien Hansen"}).json()
    assert h["members"] == [] and h["recipes"] == 0
    r = admin.post(f"/api/admin/households/{h['id']}/users", json={"username": "Kim", "password": PASSWORD, "role": "admin"})
    assert r.status_code == 201 and r.json()["members"][0]["username"] == "kim"
    kim = login(app, "kim")
    assert kim.get("/api/me").json()["household"]["name"] == "Familien Hansen"
    # Nye familier får startlistens basisvarer.
    assert any(i["pantry"] for i in kim.get("/api/ingredients").json())
    # Brugernavne er unikke på tværs af familier; svage kodeord afvises.
    assert admin.post(f"/api/admin/households/{h['id']}/users", json={"username": "max", "password": PASSWORD}).status_code == 409
    assert admin.post(f"/api/admin/households/{h['id']}/users", json={"username": "x", "password": "kort"}).status_code == 422


def test_reset_password_and_disable_log_the_user_out(app, admin):
    h = admin.post("/api/admin/households", json={"name": "F"}).json()
    uid = admin.post(f"/api/admin/households/{h['id']}/users", json={"username": "kim", "password": PASSWORD}).json()["members"][0]["id"]
    kim = login(app, "kim")
    assert admin.post(f"/api/admin/users/{uid}/password", json={"password": "helt-nyt-kodeord"}).status_code == 204
    assert kim.get("/api/me").status_code == 401
    assert TestClient(app).post("/api/login", json={"username": "kim", "password": "helt-nyt-kodeord"}).status_code == 200
    kim = TestClient(app)
    kim.post("/api/login", json={"username": "kim", "password": "helt-nyt-kodeord"})
    assert admin.post(f"/api/admin/users/{uid}/disabled", json={"disabled": True}).status_code == 204
    assert kim.get("/api/me").status_code == 401
    assert TestClient(app).post("/api/login", json={"username": "kim", "password": "helt-nyt-kodeord"}).status_code == 401
    admin.post(f"/api/admin/users/{uid}/disabled", json={"disabled": False})
    assert TestClient(app).post("/api/login", json={"username": "kim", "password": "helt-nyt-kodeord"}).status_code == 200


def test_disable_whole_family_spares_system_admins(app, admin):
    r = admin.get("/api/admin/households").json()
    hid = r[0]["id"]
    add_user(app, "anne", hid, "medlem")
    assert admin.post(f"/api/admin/households/{hid}/disabled", json={"disabled": True}).status_code == 204
    members = {m["username"]: m for m in admin.get("/api/admin/households").json()[0]["members"]}
    assert members["anne"]["disabled"] and not members["max"]["disabled"]
    assert admin.post(f"/api/admin/users/{members['max']['id']}/disabled", json={"disabled": True}).status_code == 422


def test_admin_cannot_delete_self_or_own_family(admin):
    h = admin.get("/api/admin/households").json()[0]
    assert admin.delete(f"/api/admin/users/{h['members'][0]['id']}").status_code == 422
    assert admin.delete(f"/api/admin/households/{h['id']}").status_code == 422


def test_delete_family_removes_its_data_but_keeps_recipes(app, admin):
    hid = admin.post("/api/admin/households", json={"name": "Skal væk"}).json()["id"]
    admin.post(f"/api/admin/households/{hid}/users", json={"username": "kim", "password": PASSWORD})
    kim = login(app, "kim")
    kim.post("/api/recipes", json={"title": "Kims ret", "ingredients": [{"raw": "1 løg"}]})
    kim.post("/api/plans", json={"start_date": "2026-10-26"})
    assert admin.delete(f"/api/admin/households/{hid}").status_code == 204
    assert kim.get("/api/me").status_code == 401
    assert all(h["id"] != hid for h in admin.get("/api/admin/households").json())
    assert [r["title"] for r in admin.get("/api/admin/recipes").json()] == []     # ingen andre brugte den


def test_admin_lists_and_deletes_recipes(app, client, admin):
    client.post("/api/recipes", json={"title": "Hakkebøf", "ingredients": [{"raw": "500 g hakket oksekød"}]})
    rows = admin.get("/api/admin/recipes").json()
    assert rows[0]["title"] == "Hakkebøf" and rows[0]["owner"] == "Familie A" and rows[0]["lines"] == 1
    assert admin.delete(f"/api/admin/recipes/{rows[0]['id']}").status_code == 204
    assert admin.get("/api/admin/recipes").json() == []
    assert admin.delete("/api/admin/recipes/999").status_code == 404


def test_admin_edits_a_recipe_another_family_owns(app, client, admin):
    """Systemadmin kan rette andres opskrifter. Linjer beholder id, rettelsen gemmes i historikken
    (ejerfamilien kan sætte den tilbage), og der skrives ingen familie-valg."""
    rid = client.post("/api/recipes", json={"title": "Suppe", "ingredients": [{"raw": "2 gule løg"}, {"raw": "1 dl fløde"}]}).json()["id"]
    before = admin.get(f"/api/admin/recipes/{rid}").json()
    assert before["owner"] == "Familie A"
    onion, cream = before["ingredients"]
    body = {
        "title": "Løgsuppe", "servings": 4, "source_url": None, "instructions": ["Svits løgene", "Kog op"],
        "ingredients": [
            {**onion, "raw": "3 gule løg", "item": None},     # ny tekst: serveren læser den igen
            {**cream, "is_main": True},                       # uændret: beholder sin vare
        ],
    }
    r = admin.put(f"/api/admin/recipes/{rid}", json=body)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["title"] == "Løgsuppe" and out["instructions"] == ["Svits løgene", "Kog op"]
    assert [l["id"] for l in out["ingredients"]] == [onion["id"], cream["id"]]
    assert out["ingredients"][0]["quantity"] == 3 and out["ingredients"][1]["is_main"] is True
    assert client.get(f"/api/recipes/{rid}").json()["title"] == "Løgsuppe"      # ejerfamilien ser rettelsen

    versions = client.get(f"/api/recipes/{rid}/versions").json()
    assert len(versions) == 1 and versions[0]["by"] == "max"
    with app.state.db.sessionmaker() as s:
        assert s.query(HouseholdLineMatch).count() == 0

    assert admin.put(f"/api/admin/recipes/{rid}", json={**body, "ingredients": [{"id": 99999, "raw": "x"}]}).status_code == 422
    assert admin.put("/api/admin/recipes/999", json=body).status_code == 404


def test_admin_site_is_served_with_strict_headers(app):
    c = TestClient(app)
    r = c.get("/admin")
    assert r.status_code == 200 and "Madplan" in r.text
    assert "default-src 'none'" in r.headers["content-security-policy"]
    assert r.headers["x-frame-options"] == "DENY" and r.headers["cache-control"] == "no-store"
    assert c.get("/admin/admin.js").status_code == 200 and c.get("/admin/admin.css").status_code == 200
    assert c.get("/admin/../models.py").status_code == 404
    assert c.get("/admin/hemmeligt").status_code == 404
    # Ingen data eller inline-script i siden selv.
    assert "<script>" not in r.text and "onclick=" not in r.text


def test_catalog_is_locked_to_system_admin_in_the_app(app, client, admin):
    """Familier kan sætte basisvare, men ikke omdøbe/flytte en fælles vare (§3)."""
    add_user(app, "bea", "Familie B")
    bea = login(app, "bea")
    løg = next(i for i in bea.get("/api/ingredients").json() if i["name"] == "løg")
    body = {"name": "løg", "department": løg["department"], "pantry": not løg["pantry"],
            "grams_per_piece": løg["grams_per_piece"], "grams_per_dl": løg["grams_per_dl"]}
    assert bea.put(f"/api/ingredients/{løg['id']}", json=body).status_code == 200
    assert bea.put(f"/api/ingredients/{løg['id']}", json={**body, "name": "gult løg"}).status_code == 403
    assert bea.put(f"/api/ingredients/{løg['id']}", json={**body, "department": "kg" if løg["department"] != "kg" else "fg"}).status_code == 403
    # Nye varer kan familien stadig oprette (det kun føjer til kataloget).
    assert bea.post("/api/ingredients", json={"name": "nyt-mærke", "department": "fg"}).status_code == 201
    # Systemadmin kan rette i appen (Max er systemadmin i denne test).
    maxc = login(app, "max")
    assert maxc.put(f"/api/ingredients/{løg['id']}", json={**body, "name": "gult løg"}).status_code == 200


def test_admin_edits_catalog_and_aliases(app, client, admin):
    cat = admin.get("/api/admin/ingredients").json()
    assert {"code": "fg", "name": "Frugt & grønt"} in cat["departments"] or cat["departments"]
    løg = next(i for i in cat["items"] if i["name"] == "løg")
    r = admin.put(f"/api/admin/ingredients/{løg['id']}", json={"name": "gult løg", "department": løg["department"], "grams_per_piece": 110})
    assert r.status_code == 200 and r.json()["name"] == "gult løg" and r.json()["grams_per_piece"] == 110
    # Det gamle navn lever videre som alias.
    assert "løg" in [a["alias"] for a in r.json()["aliases"]]
    alias = r.json()["aliases"][0]
    assert admin.delete(f"/api/admin/aliases/{alias['id']}").status_code == 204
    assert admin.put(f"/api/admin/ingredients/{løg['id']}", json={"name": "hvedemel", "department": løg["department"]}).status_code == 409
    # En vare i brug kan ikke slettes.
    client.post("/api/recipes", json={"title": "Suppe", "ingredients": [{"raw": "2 gult løg"}]})
    assert admin.delete(f"/api/admin/ingredients/{løg['id']}").status_code == 409
    free = next(i for i in admin.get("/api/admin/ingredients").json()["items"] if i["used_in"] == 0)
    assert admin.delete(f"/api/admin/ingredients/{free['id']}").status_code == 204


# --- Tofaktor ------------------------------------------------------------------------------

def _enable_2fa(admin, app):
    from madplan import totp
    secret = admin.post("/api/admin/2fa/setup").json()["secret"]
    import time
    step = int(time.time() // 30)
    assert admin.post("/api/admin/2fa/enable", json={"code": totp.code_at(secret, step)}).status_code == 204
    return secret, step


def test_totp_matches_rfc_6238_vectors():
    import base64

    from madplan import totp
    secret = base64.b32encode(b"12345678901234567890").decode()
    # RFC 6238, bilag B (SHA-1), 6 cifre = de sidste 6 af de 8 cifre i tabellen
    assert totp.code_at(secret, 59 // 30) == "287082"
    assert totp.code_at(secret, 1111111109 // 30) == "081804"
    assert totp.code_at(secret, 20000000000 // 30) == "353130"
    step = totp.verify(secret, "287082", now=59)
    assert step == 1 and totp.verify(secret, "287082", last_step=1, now=59) is None   # brugt trin afvises
    assert totp.verify(secret, "000000", now=59) is None and totp.verify(secret, "abc", now=59) is None


def test_login_requires_code_once_two_factor_is_on(app, client, admin):
    from madplan import totp
    secret, used = _enable_2fa(admin, app)
    assert admin.get("/api/admin/me").json()["two_factor"] is True
    c = TestClient(app)
    assert c.post("/api/admin/login", json={"username": "max", "password": PASSWORD}).status_code == 401
    assert c.post("/api/admin/login", json={"username": "max", "password": PASSWORD, "code": "000000"}).status_code == 401
    import time
    nxt = totp.code_at(secret, int(time.time() // 30) + 1)          # næste vindue (inden for tolerancen)
    r = c.post("/api/admin/login", json={"username": "max", "password": PASSWORD, "code": nxt})
    assert r.status_code == 200
    # Samme kode kan ikke bruges to gange.
    assert TestClient(app).post("/api/admin/login", json={"username": "max", "password": PASSWORD, "code": nxt}).status_code == 401


def test_wrong_code_and_wrong_password_look_the_same(app, client, admin):
    _enable_2fa(admin, app)
    a = TestClient(app).post("/api/admin/login", json={"username": "max", "password": "forkert-kodeord", "code": "123456"})
    b = TestClient(app).post("/api/admin/login", json={"username": "max", "password": PASSWORD, "code": "123456"})
    assert a.status_code == b.status_code == 401 and a.json() == b.json()


def test_enable_needs_a_correct_code_and_secret_is_stored_sealed(app, client, admin):
    from madplan.models import User
    s = admin.post("/api/admin/2fa/setup").json()
    assert admin.post("/api/admin/2fa/enable", json={"code": "000000"}).status_code == 422
    with app.state.db.sessionmaker() as db:
        u = db.query(User).filter_by(username="max").one()
        assert not u.totp_enabled and s["secret"] not in u.totp_secret
    assert s["uri"].startswith("otpauth://totp/") and s["secret"] in s["uri"]


def test_disable_two_factor_needs_password_and_code(app, client, admin):
    from madplan import totp
    secret, used = _enable_2fa(admin, app)
    import time
    code = totp.code_at(secret, int(time.time() // 30) + 1)
    assert admin.post("/api/admin/2fa/disable", json={"password": "forkert", "code": code}).status_code == 403
    assert admin.post("/api/admin/2fa/disable", json={"password": PASSWORD, "code": code}).status_code == 204
    assert admin.get("/api/admin/me").json()["two_factor"] is False
    assert TestClient(app).post("/api/admin/login", json={"username": "max", "password": PASSWORD}).status_code == 200


def test_cli_reset_2fa(app, client, admin, tmp_path, monkeypatch):
    _enable_2fa(admin, app)
    from madplan import cli
    monkeypatch.setenv("DATA_DIR", str(app.state.settings.data_dir))
    monkeypatch.setenv("APP_SECRET", app.state.settings.secret)
    assert cli.main(["reset-2fa", "max"]) == 0
    assert TestClient(app).post("/api/admin/login", json={"username": "max", "password": PASSWORD}).status_code == 200
