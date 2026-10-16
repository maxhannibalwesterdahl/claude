"""Adgangskontrol og adskillelse mellem familier (docs/flere-familier.md §6).

Test-matrixen opretter to familier og kalder HVER rute med den anden families
id'er. En ny rute skal med i `CASES` (eller i `NO_FOREIGN_IDS`), ellers fejler
`test_every_route_is_in_the_matrix`.
"""

import re

import pytest
from fastapi.testclient import TestClient

from conftest import PASSWORD, add_user, login
from madplan.models import User


def _routes(app):
    """Alle /api-ruter (fra OpenAPI-skemaet) undtagen login og helbred."""
    skip = {"/api/login", "/api/logout", "/api/health", "/api/{rest}",
            "/api/invites/{token}", "/api/invites/{token}/accept"}   # åbnes af den inviterede (test_household.py)
    for path, ops in app.openapi()["paths"].items():
        # /api/admin har sin egen matrix (test_admin.py): 404 uden admin-session.
        if path.startswith("/api") and not path.startswith("/api/admin") and path not in skip:
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
def colleague(app, client):
    """Anne, i samme familie som Max."""
    add_user(app, "anne", "Familie A", "medlem")
    return login(app, "anne")


@pytest.fixture
def other(app, client):
    """Bea, i en anden familie."""
    add_user(app, "bea", "Familie B")
    return login(app, "bea")


def _seed(client):
    rid = client.post("/api/recipes", json={"title": "Familie A's ret", "child_note": "uden chili",
                                            "ingredients": [{"raw": "500 g hakket oksekød"}]}).json()
    plan = client.post("/api/plans", json={"start_date": "2026-10-26", "days": 7}).json()
    p = client.put(f"/api/plans/{plan['id']}/slots", json={"date": "2026-10-26", "kind": "opskrift", "recipe_id": rid["id"]}).json()
    meal = p["days"][0]["meal"]
    p = client.post(f"/api/meals/{meal['id']}/reminders", json={"text": "kød op"}).json()
    p = client.post(f"/api/plans/{plan['id']}/wishlist", json={"text": "pizza"}).json()
    shop = client.post("/api/shopping/extras?plan_id=%d" % plan["id"], json={"text": "bleer"}).json()
    client.put(f"/api/recipes/{rid['id']}", json={"title": "Familie A's ret", "child_note": "uden chili",
                                                  "ingredients": [{"raw": "500 g hakket oksekød"}]})
    adj = client.post(f"/api/recipes/{rid['id']}/adjustments/extra", json={"raw": "1 dåse majs"}).json()
    invite = client.post("/api/household/invites", json={}).json()
    return {
        "adjustment_id": adj["extra_lines"][0]["id"], "version_id": client.get(f"/api/recipes/{rid['id']}/versions").json()[0]["id"], "invite_id": invite["id"], "user_id": client.get("/api/me").json()["id"],
        "recipe_id": rid["id"], "line_id": rid["ingredients"][0]["id"], "plan_id": plan["id"],
        "meal_id": meal["id"], "reminder_id": p["days"][0]["meal"]["reminders"][0]["id"],
        "wish_id": p["wishlist"][0]["id"],
        "extra_id": next(i["key"] for i in shop["items"] if i["name"] == "bleer").removeprefix("e:"),
    }


def test_users_in_same_family_share_everything(client, colleague):
    """Inden for én familie ser Max og Anne det samme."""
    ids = _seed(client)
    assert colleague.get(f"/api/recipes/{ids['recipe_id']}").json()["child_note"] == "uden chili"
    assert colleague.get(f"/api/plans/{ids['plan_id']}").status_code == 200
    names = [i["name"] for i in colleague.get(f"/api/shopping?plan_id={ids['plan_id']}").json()["items"]]
    assert "bleer" in names
    assert colleague.put(f"/api/recipes/{ids['recipe_id']}", json={"title": "Rettet af Anne"}).status_code == 200


# --- Matrixen ------------------------------------------------------------------------
# (metode, sti) -> (json eller None, forventet svar fra den ANDEN familie)
# Sti-parametre fyldes ud med den første families id'er.

CASES: dict[tuple[str, str], tuple[dict | None, int]] = {
    # opskrifter: fælles at læse, kun ejerfamilien retter
    ("PUT", "/api/recipes/{recipe_id}"): ({"title": "Overtaget"}, 404),
    ("GET", "/api/recipes/{recipe_id}/versions"): (None, 404),
    ("POST", "/api/recipes/{recipe_id}/versions/{version_id}/restore"): (None, 404),
    ("DELETE", "/api/recipes/{recipe_id}"): (None, 404),
    ("DELETE", "/api/recipes/{recipe_id}/image"): (None, 404),
    ("POST", "/api/recipes/{recipe_id}/suggest-main"): (None, 404),
    ("PUT", "/api/lines/{line_id}/main"): ({"is_main": True}, 404),
    # planer
    ("GET", "/api/plans/{plan_id}"): (None, 404),
    ("DELETE", "/api/plans/{plan_id}"): (None, 404),
    ("PUT", "/api/plans/{plan_id}/slots"): ({"date": "2026-10-27", "kind": "fritekst", "text": "x"}, 404),
    ("POST", "/api/plans/{plan_id}/wishlist"): ({"text": "x"}, 404),
    ("POST", "/api/plans/{plan_id}/wishlist/distribute"): (None, 404),
    ("DELETE", "/api/wishlist/{wish_id}"): (None, 404),
    ("POST", "/api/wishlist/{wish_id}/place"): ({"date": "2026-10-27"}, 404),
    ("PATCH", "/api/meals/{meal_id}"): ({"multiplier": 2}, 404),
    ("POST", "/api/meals/{meal_id}/move"): ({"date": "2026-10-27"}, 404),
    ("DELETE", "/api/meals/{meal_id}"): (None, 404),
    ("PUT", "/api/meals/{meal_id}/lines/{line_id}"): ({"state": "hjemme"}, 404),
    ("POST", "/api/meals/{meal_id}/reminders"): ({"text": "x"}, 404),
    ("PATCH", "/api/reminders/{reminder_id}"): ({"done": True}, 404),
    ("DELETE", "/api/reminders/{reminder_id}"): (None, 404),
    ("GET", "/api/suggestions?plan_id={plan_id}"): (None, 404),
    ("DELETE", "/api/recipes/{recipe_id}/adjustments/{adjustment_id}"): (None, 404),
    # indkøb
    ("GET", "/api/shopping?plan_id={plan_id}"): (None, 404),
    ("POST", "/api/shopping/extras?plan_id={plan_id}"): ({"text": "x"}, 404),
    ("PATCH", "/api/shopping/extras/{extra_id}"): ({"ingredient_id": None}, 404),
    ("DELETE", "/api/shopping/extras/{extra_id}"): (None, 404),
    ("POST", "/api/shopping/home"): ({"plan_id": "{plan_id}", "key": "i:1", "home": True}, 404),
    # familiens indstillinger (Bea er admin i sin egen familie, men Max er ikke hendes medlem)
    ("DELETE", "/api/household/invites/{invite_id}"): (None, 404),
    ("POST", "/api/household/members/{user_id}/password"): ({"password": "et-helt-nyt-kodeord"}, 404),
    ("DELETE", "/api/household/members/{user_id}"): (None, 404),
    ("PUT", "/api/household/members/{user_id}/role"): ({"role": "medlem"}, 404),
    # sync svarer altid med den andens egen uge og gemmer intet på en fremmed plan
    ("POST", "/api/shopping/sync"): ({"plan_id": "{plan_id}", "changes": [], "view_plan_id": "{plan_id}"}, 200),
}

# Ruter, der ikke tager en anden families id'er: egne lister, fælles opskrifter og
# varekatalog (delt viden, flere-familier.md §1), indstillinger pr. familie, login.
NO_FOREIGN_IDS = {
    ("GET", "/api/me"), ("GET", "/api/meta"), ("POST", "/api/parse"),
    ("GET", "/api/recipes"), ("POST", "/api/recipes"), ("POST", "/api/recipes/import"),
    ("GET", "/api/recipes/{recipe_id}"),          # fælles at læse (tjekkes i test_shared_recipe_is_readable_but_not_editable)
    ("POST", "/api/recipes/{recipe_id}/collection"), ("DELETE", "/api/recipes/{recipe_id}/collection"),
    ("PUT", "/api/recipes/{recipe_id}/adjustments/lines/{line_id}"), ("POST", "/api/recipes/{recipe_id}/adjustments/extra"),
    ("PUT", "/api/recipes/{recipe_id}/adjustments/note"),   # kun egne tilpasninger: test_tilpasninger.py
    ("PUT", "/api/recipes/{recipe_id}/favorite"), ("PUT", "/api/recipes/{recipe_id}/note"),   # kun egen samling/note: test_samling.py
    ("POST", "/api/recipes/{recipe_id}/image"),   # som PUT: se test_other_family_cannot_upload_image
    ("GET", "/api/review"),
    ("POST", "/api/lines/{line_id}/confirm"), ("POST", "/api/lines/{line_id}/ignore"),   # familiens eget lag: test_varekobling.py
    ("GET", "/api/search/valdemarsro"), ("GET", "/api/search/nemlig"),
    ("GET", "/api/ingredients"), ("POST", "/api/ingredients"), ("PUT", "/api/ingredients/{ingredient_id}"),
    ("GET", "/api/images/{name}"),
    ("GET", "/api/plans"), ("POST", "/api/plans"), ("GET", "/api/plans/current"),
    ("GET", "/api/household"), ("PATCH", "/api/household"), ("POST", "/api/household/invites"),
    ("POST", "/api/me/password"), ("GET", "/api/household/export"), ("POST", "/api/household/erase"),
    ("GET", "/api/shopping"),
    ("GET", "/api/settings/departments"), ("PUT", "/api/settings/departments"),
    ("GET", "/api/push/key"), ("POST", "/api/push/subscriptions"),
}


def test_every_route_is_in_the_matrix(app):
    """Nye ruter skal med i matrixen (eller forklares i NO_FOREIGN_IDS)."""
    known = set(CASES) | NO_FOREIGN_IDS
    # Forespørgselsparametre står ikke i OpenAPI-stien; match på stien alene.
    by_path = {(m, p.split("?")[0]) for (m, p) in known}
    missing = [r for r in _routes(app) if r not in by_path]
    assert not missing, f"Ruter uden i adgangsmatrixen: {missing}"


def _fill(value, ids):
    if isinstance(value, str):
        return int(ids[value[1:-1]]) if re.fullmatch(r"\{\w+\}", value) else value.format(**ids)
    if isinstance(value, dict):
        return {k: _fill(v, ids) for k, v in value.items()}
    return value


@pytest.mark.parametrize("method,path", sorted(CASES), ids=lambda v: v if isinstance(v, str) else None)
def test_other_family_gets_404_on_every_id(client, other, method, path):
    ids = _seed(client)
    body, expected = CASES[(method, path)]
    r = other.request(method, path.format(**ids), json=_fill(body, ids) if body is not None else None)
    assert r.status_code == expected, f"{method} {path}: {r.status_code} {r.text}"
    # Familie A's data er uændret, uanset hvad der blev kaldt.
    assert client.get(f"/api/recipes/{ids['recipe_id']}").json()["title"] == "Familie A's ret"
    plan = client.get(f"/api/plans/{ids['plan_id']}").json()
    meal = plan["days"][0]["meal"]
    assert meal["title"] == "Familie A's ret" and meal["multiplier"] == 1.0
    assert [r["text"] for r in meal["reminders"]] == ["kød op"] and not meal["reminders"][0]["done"]
    assert [w["text"] for w in plan["wishlist"]] == ["pizza"]
    names = [i["name"] for i in client.get(f"/api/shopping?plan_id={ids['plan_id']}").json()["items"]]
    assert "bleer" in names
    line = client.get(f"/api/recipes/{ids['recipe_id']}").json()["ingredients"][0]
    assert not line["is_main"] or line["match_status"] != "bekræftet"   # confirm/main/ignore ramte ikke


def test_other_family_cannot_upload_image(client, other):
    ids = _seed(client)
    r = other.post(f"/api/recipes/{ids['recipe_id']}/image", files={"file": ("a.png", b"\x89PNG\r\n\x1a\n" + b"0" * 20)})
    assert r.status_code == 404
    assert client.get(f"/api/recipes/{ids['recipe_id']}").json()["image_url"] is None


def test_shared_recipe_is_readable_but_not_editable(client, other):
    """Opskrifter er fælles at bruge (§1) men kun ejerfamilien retter dem (§4)."""
    ids = _seed(client)
    mine = client.get(f"/api/recipes/{ids['recipe_id']}").json()
    theirs = other.get(f"/api/recipes/{ids['recipe_id']}").json()
    assert (mine["owned"], theirs["owned"]) == (True, False)
    assert theirs["title"] == mine["title"] and theirs["child_note"] == ""   # noten er privat
    assert other.get("/api/recipes").json() == []                       # ikke i Bea's samling
    listed = {r["id"]: r for r in other.get("/api/recipes?alle=true").json()}
    assert listed[ids["recipe_id"]]["owned"] is False and listed[ids["recipe_id"]]["to_review"] == 0
    # ... og kan sættes på den andens plan.
    plan = other.post("/api/plans", json={"start_date": "2026-10-26"}).json()
    r = other.put(f"/api/plans/{plan['id']}/slots", json={"date": "2026-10-26", "kind": "opskrift", "recipe_id": ids["recipe_id"]})
    assert r.status_code == 200
    # Ejeren kan nu ikke slette den, mens en anden familie bruger den.
    assert client.delete(f"/api/recipes/{ids['recipe_id']}").status_code == 409
    other.delete(f"/api/plans/{plan['id']}")
    assert client.delete(f"/api/recipes/{ids['recipe_id']}").status_code == 409     # den ligger i Beas samling
    other.delete(f"/api/recipes/{ids['recipe_id']}/collection")
    assert client.delete(f"/api/recipes/{ids['recipe_id']}").status_code == 204


def test_other_family_cannot_see_plans_or_shopping(client, other):
    ids = _seed(client)
    assert other.get("/api/plans").json() == []
    assert other.get("/api/plans/current").status_code == 404
    assert other.get("/api/shopping").json()["items"] == []
    # Samme datoer er frie for den anden familie (overlap tælles pr. familie).
    assert other.post("/api/plans", json={"start_date": "2026-10-26"}).status_code == 201
    assert client.get("/api/plans").json()[0]["id"] == ids["plan_id"]


def test_sync_from_other_family_changes_nothing(client, other):
    ids = _seed(client)
    key = f"e:{ids['extra_id']}"
    other.post("/api/shopping/sync", json={"plan_id": ids["plan_id"], "changes": [
        {"key": key, "checked": True, "ts": 9_999_999_999_999}, {"key": "i:1", "checked": True, "ts": 1, "plan_id": ids["plan_id"]}]})
    items = client.get(f"/api/shopping?plan_id={ids['plan_id']}").json()["items"]
    assert not any(i["checked"] for i in items)


def test_other_family_cannot_change_departments_or_pantry(client, other):
    order = [d["code"] for d in client.get("/api/settings/departments").json()]
    other.put("/api/settings/departments", json={"order": order[::-1]})
    assert [d["code"] for d in client.get("/api/settings/departments").json()] == order
    assert [d["code"] for d in other.get("/api/settings/departments").json()] == order[::-1]
    # Basisvarer er pr. familie.
    salt = next(i for i in client.get("/api/ingredients").json() if i["name"] == "salt")
    body = {"name": "salt", "department": salt["department"], "pantry": not salt["pantry"]}
    assert other.put(f"/api/ingredients/{salt['id']}", json=body).status_code == 200
    mine = next(i for i in client.get("/api/ingredients").json() if i["name"] == "salt")
    theirs = next(i for i in other.get("/api/ingredients").json() if i["name"] == "salt")
    assert mine["pantry"] == salt["pantry"] and theirs["pantry"] == (not salt["pantry"])


def test_family_note_is_private(client, other):
    """Note om barnet er pr. familie (flere-familier.md §1)."""
    ids = _seed(client)
    assert other.get(f"/api/recipes/{ids['recipe_id']}").json()["child_note"] == ""
    assert client.get(f"/api/recipes/{ids['recipe_id']}").json()["child_note"] == "uden chili"


def test_other_family_cannot_touch_reminders_and_meals(client, other):
    ids = _seed(client)
    assert other.post(f"/api/meals/{ids['meal_id']}/reminders", json={"text": "x"}).status_code == 404
    assert other.delete(f"/api/meals/{ids['meal_id']}").status_code == 404


def test_review_lists_only_own_recipes(client, other):
    client.post("/api/recipes", json={"title": "A", "ingredients": [{"raw": "1 knivspids zzzxqy"}]})
    assert [l["item"] for l in client.get("/api/review").json()] == ["zzzxqy"]
    assert other.get("/api/review").json() == []


def test_user_without_family_is_refused(app, client):
    with app.state.db.sessionmaker() as s:
        from madplan.auth import hash_password
        s.add(User(username="uden", password_hash=hash_password(PASSWORD)))
        s.commit()
    c = login(app, "uden")
    assert c.get("/api/me").json()["household"] is None
    for path in ("/api/plans", "/api/recipes", "/api/shopping"):
        assert c.get(path).status_code == 403


def test_me_tells_family_and_role(client, colleague):
    me = client.get("/api/me").json()
    assert me["household"]["name"] == "Familie A" and me["household"]["role"] == "admin"
    assert me["is_system_admin"] is False
    assert colleague.get("/api/me").json()["household"]["role"] == "medlem"


def test_session_cookie_from_deleted_user_is_rejected(app, client):
    with app.state.db.sessionmaker() as s:
        s.delete(s.get(User, 1))
        s.commit()
    assert client.get("/api/me").status_code == 401
