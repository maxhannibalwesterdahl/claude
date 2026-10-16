"""QA: adgangskontrol og adskillelse mellem familier.

Flere familier er endnu ikke bygget (docs/flere-familier.md): der findes ingen
`household`-tabel, og alle brugere deler alle data. Testene med xfail beskriver,
hvad der SKAL gælde, før en anden familie lukkes ind. De skal omskrives til at
oprette to familier, når CurrentHousehold findes (se afsnit 6 i designet).
"""

import re

import pytest
from fastapi.testclient import TestClient

from conftest import PASSWORD
from madplan.auth import hash_password
from madplan.models import User

NO_HOUSEHOLDS = "Flere familier er ikke bygget: alle brugere deler alle data (docs/flere-familier.md)"


def _routes(app):
    """Alle /api-ruter (fra OpenAPI-skemaet) undtagen login og helbred."""
    skip = {"/api/login", "/api/logout", "/api/health", "/api/{rest}"}
    for path, ops in app.openapi()["paths"].items():
        if path.startswith("/api") and path not in skip:
            for method in ops:
                yield method.upper(), path


def test_every_api_route_requires_login(app, anon):
    """Matrix: hver eneste rute (også nye) svarer 401 uden login."""
    routes = list(_routes(app))
    assert len(routes) >= 40  # sikrer, at matrixen faktisk finder ruterne
    for method, path in routes:
        url = re.sub(r"\{[^}]+\}", "1", path)
        r = anon.request(method, url, json={})
        assert r.status_code == 401, f"{method} {path} svarede {r.status_code} uden login"


@pytest.fixture
def second_user(app, client):
    with app.state.db.sessionmaker() as s:
        s.add(User(username="anne", password_hash=hash_password(PASSWORD)))
        s.commit()
    other = TestClient(app)
    assert other.post("/api/login", json={"username": "anne", "password": PASSWORD}).status_code == 200
    return other


def _seed(client):
    rid = client.post("/api/recipes", json={"title": "Familie A's ret", "child_note": "uden chili",
                                            "ingredients": [{"raw": "500 g hakket oksekød"}]}).json()["id"]
    plan = client.post("/api/plans", json={"start_date": "2026-10-26"}).json()
    client.put(f"/api/plans/{plan['id']}/slots", json={"date": "2026-10-26", "kind": "opskrift", "recipe_id": rid})
    client.post("/api/shopping/extras?plan_id=%d" % plan["id"], json={"text": "bleer"})
    return rid, plan["id"]


def test_users_in_same_family_share_everything(client, second_user):
    """Nuværende (og tilsigtede) adfærd inden for én familie: Max og Anne ser det samme."""
    rid, pid = _seed(client)
    assert second_user.get(f"/api/recipes/{rid}").status_code == 200
    assert second_user.get(f"/api/plans/{pid}").status_code == 200
    names = [i["name"] for i in second_user.get(f"/api/shopping?plan_id={pid}").json()["items"]]
    assert "bleer" in names


@pytest.mark.xfail(reason=NO_HOUSEHOLDS, strict=False)
def test_other_family_cannot_see_plans_or_shopping(client, second_user):
    rid, pid = _seed(client)
    assert second_user.get("/api/plans").json() == []
    assert second_user.get(f"/api/plans/{pid}").status_code == 404
    assert second_user.get(f"/api/shopping?plan_id={pid}").status_code == 404
    assert second_user.delete(f"/api/plans/{pid}").status_code == 404


@pytest.mark.xfail(reason=NO_HOUSEHOLDS, strict=False)
def test_other_family_cannot_change_departments_or_pantry(client, second_user):
    order = [d["code"] for d in client.get("/api/settings/departments").json()]
    second_user.put("/api/settings/departments", json={"order": order[::-1]})
    assert [d["code"] for d in client.get("/api/settings/departments").json()] == order


@pytest.mark.xfail(reason=NO_HOUSEHOLDS, strict=False)
def test_family_note_is_private(client, second_user):
    """Note om barnet er pr. familie (flere-familier.md §1)."""
    rid, _ = _seed(client)
    assert second_user.get(f"/api/recipes/{rid}").json()["child_note"] == ""


@pytest.mark.xfail(reason=NO_HOUSEHOLDS, strict=False)
def test_other_family_cannot_edit_or_delete_shared_recipe(client, second_user):
    """En opskrift i en anden families plan må ikke kunne slettes (flere-familier.md §4)."""
    rid, _ = _seed(client)
    assert second_user.delete(f"/api/recipes/{rid}").status_code in (404, 409)
    assert client.get(f"/api/recipes/{rid}").status_code == 200


@pytest.mark.xfail(reason=NO_HOUSEHOLDS, strict=False)
def test_other_family_cannot_touch_reminders_and_meals(client, second_user):
    _, pid = _seed(client)
    meal = client.get(f"/api/plans/{pid}").json()["days"][0]["meal"]
    assert second_user.post(f"/api/meals/{meal['id']}/reminders", json={"text": "x"}).status_code == 404
    assert second_user.delete(f"/api/meals/{meal['id']}").status_code == 404


def test_session_cookie_from_deleted_user_is_rejected(app, client):
    with app.state.db.sessionmaker() as s:
        s.delete(s.get(User, 1))
        s.commit()
    assert client.get("/api/me").status_code == 401
