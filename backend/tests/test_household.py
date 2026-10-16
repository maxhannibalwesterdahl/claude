"""Familiens indstillinger og invitationer (flere-familier.md §5)."""

import pytest
from fastapi.testclient import TestClient

from conftest import PASSWORD, add_user, login

NEW_PW = "helt-nyt-kodeord-1"


@pytest.fixture
def colleague(app, client):
    add_user(app, "anne", "Familie A", "medlem")
    return login(app, "anne")


def _join(app, token, username="kim", password=PASSWORD):
    c = TestClient(app)
    return c, c.post(f"/api/invites/{token}/accept", json={"username": username, "password": password})


def test_view_household(client, colleague):
    v = client.get("/api/household").json()
    assert v["name"] == "Familie A" and v["role"] == "admin"
    assert [(m["username"], m["role"], m["you"]) for m in v["members"]] == [("anne", "medlem", False), ("max", "admin", True)]
    # Et medlem ser medlemmerne, men ikke invitationerne.
    client.post("/api/household/invites", json={})
    assert colleague.get("/api/household").json()["invites"] == []
    assert len(client.get("/api/household").json()["invites"]) == 1


def test_only_family_admin_can_manage(client, colleague):
    me = client.get("/api/me").json()["id"]
    for method, path, body in [
        ("PATCH", "/api/household", {"name": "x"}), ("POST", "/api/household/invites", {}),
        ("POST", f"/api/household/members/{me}/password", {"password": NEW_PW}),
        ("DELETE", f"/api/household/members/{me}", None), ("PUT", f"/api/household/members/{me}/role", {"role": "medlem"}),
    ]:
        assert colleague.request(method, path, json=body).status_code == 403, (method, path)


def test_rename_family(client):
    assert client.patch("/api/household", json={"name": "  Familien   Berg "}).json()["name"] == "Familien Berg"
    assert client.get("/api/me").json()["household"]["name"] == "Familien Berg"
    assert client.patch("/api/household", json={"name": "   "}).status_code == 422


def test_invite_flow(app, client):
    inv = client.post("/api/household/invites", json={"role": "medlem"}).json()
    anon = TestClient(app)
    assert anon.get(f"/api/invites/{inv['token']}").json() == {"household": "Familie A", "role": "medlem"}
    kim, r = _join(app, inv["token"])
    assert r.status_code == 201 and r.json()["household"]["name"] == "Familie A" and r.json()["household"]["role"] == "medlem"
    assert kim.get("/api/me").json()["username"] == "kim"            # logget ind med det samme
    # Linket virker kun én gang, og er væk fra listen.
    assert anon.get(f"/api/invites/{inv['token']}").status_code == 404
    assert _join(app, inv["token"], "lis")[1].status_code == 404
    assert client.get("/api/household").json()["invites"] == []
    # Kim ser familiens data.
    client.post("/api/plans", json={"start_date": "2026-10-26"})
    assert len(kim.get("/api/plans").json()) == 1


def test_invite_rules(app, client):
    inv = client.post("/api/household/invites", json={"role": "admin"}).json()
    assert _join(app, inv["token"], "max")[1].status_code == 409          # brugernavnet er optaget
    assert _join(app, inv["token"], "med mellemrum")[1].status_code == 422
    assert _join(app, inv["token"], "kim", "kort")[1].status_code == 422
    c, r = _join(app, inv["token"], "Kim")
    assert r.status_code == 201 and r.json()["username"] == "kim" and r.json()["household"]["role"] == "admin"
    assert TestClient(app).get("/api/invites/ukendt-nøgle").status_code == 404


def test_invite_expires_and_can_be_revoked(app, client):
    from datetime import timedelta

    from madplan.models import Invite, utcnow
    a = client.post("/api/household/invites", json={}).json()
    b = client.post("/api/household/invites", json={}).json()
    assert client.delete(f"/api/household/invites/{b['id']}").status_code == 204
    assert TestClient(app).get(f"/api/invites/{b['token']}").status_code == 404
    with app.state.db.sessionmaker() as s:
        s.get(Invite, a["id"]).expires_at = utcnow() - timedelta(minutes=1)
        s.commit()
    assert TestClient(app).get(f"/api/invites/{a['token']}").status_code == 404
    assert client.get("/api/household").json()["invites"] == []


def test_token_is_not_stored_in_clear(app, client):
    inv = client.post("/api/household/invites", json={}).json()
    with app.state.db.sessionmaker() as s:
        from madplan.models import Invite
        assert inv["token"] not in s.get(Invite, inv["id"]).token_hash
        assert len(inv["token"]) >= 40


def test_reset_member_password_logs_member_out(app, client, colleague):
    anne = next(m["id"] for m in client.get("/api/household").json()["members"] if m["username"] == "anne")
    assert client.post(f"/api/household/members/{anne}/password", json={"password": "kort"}).status_code == 422
    assert client.post(f"/api/household/members/{anne}/password", json={"password": NEW_PW}).status_code == 204
    assert colleague.get("/api/me").status_code == 401
    assert TestClient(app).post("/api/login", json={"username": "anne", "password": NEW_PW}).status_code == 200


def test_remove_member_and_last_admin_rules(client, colleague):
    v = client.get("/api/household").json()
    ids = {m["username"]: m["id"] for m in v["members"]}
    assert client.delete(f"/api/household/members/{ids['max']}").status_code == 422        # ikke sig selv
    assert client.put(f"/api/household/members/{ids['max']}/role", json={"role": "medlem"}).status_code == 422  # sidste admin
    assert client.put(f"/api/household/members/{ids['anne']}/role", json={"role": "admin"}).status_code == 204
    assert client.put(f"/api/household/members/{ids['max']}/role", json={"role": "medlem"}).status_code == 204
    assert colleague.delete(f"/api/household/members/{ids['max']}").status_code == 204    # Anne er admin nu
    assert client.get("/api/me").status_code == 401


def test_change_own_password(app, client):
    other_device = login(app, "max")
    assert client.post("/api/me/password", json={"current": "forkert", "new": NEW_PW}).status_code == 403
    assert client.post("/api/me/password", json={"current": PASSWORD, "new": "kort"}).status_code == 422
    assert client.post("/api/me/password", json={"current": PASSWORD, "new": NEW_PW}).status_code == 200
    assert client.get("/api/me").status_code == 200            # denne enhed er stadig logget ind
    assert other_device.get("/api/me").status_code == 401      # de andre er logget ud
    assert TestClient(app).post("/api/login", json={"username": "max", "password": NEW_PW}).status_code == 200


def test_admin_can_make_invite_for_a_family(app, client):
    from madplan.models import User
    with app.state.db.sessionmaker() as s:
        s.query(User).filter_by(username="max").one().is_system_admin = True
        s.commit()
    admin = TestClient(app)
    assert admin.post("/api/admin/login", json={"username": "max", "password": PASSWORD}).status_code == 200
    hid = admin.post("/api/admin/households", json={"name": "Ny familie"}).json()["id"]
    inv = admin.post(f"/api/admin/households/{hid}/invites", json={}).json()
    assert inv["path"] == f"/join/{inv['token']}"
    _, r = _join(app, inv["token"], "nyfamilie")
    assert r.json()["household"] == {"id": hid, "name": "Ny familie", "role": "admin"}
