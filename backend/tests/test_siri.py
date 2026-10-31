from conftest import add_user, login

from madplan.api.siri import split_items


def key(client) -> str:
    return client.post("/api/me/keys", json={"name": "Max' iPhone"}).json()["token"]


def siri(client, token, text, today="2026-11-03"):
    return client.post(f"/api/siri/add?today={today}", json={"text": text}, headers={"Authorization": f"Bearer {token}"})


def plans(client):
    return sorted((p["start_date"], p["end_date"]) for p in client.get("/api/plans").json())


def extras(client, plan_id):
    data = client.get(f"/api/shopping?plan_id={plan_id}&today=2026-11-03").json()
    return sorted(i["name"] for i in data["items"] if i["kind"] == "extra")


def test_split_items():
    assert split_items("Mælk, æg og 2 pk bleer.") == ["mælk", "æg", "2 pk bleer"]
    assert split_items("MSG") == ["MSG"]
    assert split_items(" , . ") == []


def test_adds_to_next_week(client):
    this = client.post("/api/plans", json={"start_date": "2026-11-01", "days": 7}).json()
    nxt = client.post("/api/plans", json={"start_date": "2026-11-08", "days": 7}).json()
    token = key(client)
    r = siri(client, token, "Mælk og kaffe")
    assert r.status_code == 200 and r.text == "Mælk og kaffe er tilføjet til ugen fra 8/11."
    assert extras(client, nxt["id"]) == ["kaffe", "mælk"]
    assert extras(client, this["id"]) == []
    # Samme vare igen kommer ikke på to gange.
    assert siri(client, token, "mælk og bleer").text == "Bleer er tilføjet til ugen fra 8/11. Mælk stod der allerede."
    assert siri(client, token, "mælk").text == "Mælk står allerede på listen for ugen fra 8/11."


def test_creates_next_week_in_same_rhythm(client):
    client.post("/api/plans", json={"start_date": "2026-11-01", "days": 7})
    token = key(client)
    assert siri(client, token, "bleer").text == "Bleer er tilføjet til ugen fra 8/11."
    assert plans(client) == [("2026-11-01", "2026-11-07"), ("2026-11-08", "2026-11-14")]
    # Den nye uge bruges næste gang, der kommer ikke endnu en.
    siri(client, token, "kaffe")
    assert len(plans(client)) == 2


def test_no_week_running(client):
    # Seneste uge er slut: næste uge følger rytmen frem til efter i dag.
    client.post("/api/plans", json={"start_date": "2026-10-11", "days": 7})
    assert siri(client, key(client), "bleer").text == "Bleer er tilføjet til ugen fra 8/11."
    # En kommende uge, der ikke er begyndt, er "næste uge".
    client.post("/api/plans", json={"start_date": "2026-11-05", "days": 3})
    assert siri(client, key(client), "kaffe").text == "Kaffe er tilføjet til ugen fra 5/11."


def test_without_any_week(client):
    r = siri(client, key(client), "mælk")
    assert r.status_code == 409 and plans(client) == []


def test_bad_or_deleted_key(client):
    client.post("/api/plans", json={"start_date": "2026-11-01", "days": 7})
    assert siri(client, "mp_forkert", "mælk").status_code == 401
    assert client.post("/api/siri/add", json={"text": "mælk"}).status_code == 401
    token = key(client)
    keys = client.get("/api/me/keys").json()
    assert [k["name"] for k in keys] == ["Max' iPhone"] and keys[0]["last_used_at"] is None
    assert siri(client, token, "mælk").status_code == 200
    assert client.get("/api/me/keys").json()[0]["last_used_at"] is not None
    assert client.delete(f"/api/me/keys/{keys[0]['id']}").status_code == 204
    assert siri(client, token, "kaffe").status_code == 401
    assert siri(client, token, "").status_code == 401


def test_key_belongs_to_own_household(app, client):
    client.post("/api/plans", json={"start_date": "2026-11-01", "days": 7})
    add_user(app, "ole", "Familie B")
    ole = login(app, "ole")
    ole.post("/api/plans", json={"start_date": "2026-11-01", "days": 7})
    token = key(ole)
    assert siri(ole, token, "kaffe").status_code == 200
    # Max kan hverken se eller slette Oles nøgle, og kaffen er ikke på Max' liste.
    assert client.get("/api/me/keys").json() == []
    ole_key = ole.get("/api/me/keys").json()[0]["id"]
    assert client.delete(f"/api/me/keys/{ole_key}").status_code == 404
    mine = [p for p in client.get("/api/plans").json()]
    assert all(extras(client, p["id"]) == [] for p in mine)


def test_keys_need_login(anon):
    assert anon.get("/api/me/keys").status_code == 401
    assert anon.post("/api/me/keys", json={}).status_code == 401
