"""Admin-siden (docs/flere-familier.md §5a): kun systemadmin, 404 til alle andre."""

import re

import pytest
from fastapi.testclient import TestClient

from conftest import PASSWORD, add_user, login
from madplan.models import User


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
    assert [r["owner"] for r in admin.get("/api/admin/recipes").json() if r["title"] == "Kims ret"] == [None]


def test_admin_lists_and_deletes_recipes(app, client, admin):
    client.post("/api/recipes", json={"title": "Hakkebøf", "ingredients": [{"raw": "500 g hakket oksekød"}]})
    rows = admin.get("/api/admin/recipes").json()
    assert rows[0]["title"] == "Hakkebøf" and rows[0]["owner"] == "Familie A" and rows[0]["lines"] == 1
    assert admin.delete(f"/api/admin/recipes/{rows[0]['id']}").status_code == 204
    assert admin.get("/api/admin/recipes").json() == []
    assert admin.delete("/api/admin/recipes/999").status_code == 404


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
