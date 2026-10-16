"""Historik og fortryd: opskriftsversioner (ejerfamilien) og kataloghistorik (systemadmin)."""

import pytest
from fastapi.testclient import TestClient

from conftest import PASSWORD, add_user, login, make_system_admin


def recipe(c):
    return c.post("/api/recipes", json={"title": "Sovs", "instructions": ["Steg"], "servings": 4,
                                        "ingredients": [{"raw": "500 g hakket oksekød"}, {"raw": "1 løg"}]}).json()


def edit(c, r, **changes):
    body = {"title": r["title"], "servings": r["servings"], "instructions": r["instructions"],
            "ingredients": [{k: v for k, v in l.items() if k not in ("ingredient", "skipped", "my_quantity")}
                            | ({"ingredient_id": l["ingredient"]["id"]} if l["ingredient"] else {}) for l in r["ingredients"]]}
    body.update(changes)
    return c.put(f"/api/recipes/{r['id']}", json=body).json()


@pytest.fixture
def other(app, client):
    add_user(app, "bea", "Familie B")
    return login(app, "bea")


def test_every_edit_saves_the_old_version_and_can_be_restored(client):
    r = recipe(client)
    r2 = edit(client, r, title="Sovs 2", ingredients=[r["ingredients"][0] | {"raw": "600 g hakket oksekød", "item": "hakket oksekød"}])
    assert r2["title"] == "Sovs 2" and len(r2["ingredients"]) == 1
    versions = client.get(f"/api/recipes/{r['id']}/versions").json()
    assert len(versions) == 1 and versions[0]["title"] == "Sovs" and versions[0]["lines"] == 2 and versions[0]["by"] == "max"
    back = client.post(f"/api/recipes/{r['id']}/versions/{versions[0]['id']}/restore").json()
    assert back["title"] == "Sovs" and [l["raw"] for l in back["ingredients"]] == ["500 g hakket oksekød", "1 løg"]
    # Linjen, der blev bevaret, har samme id (planer peger på den); fortrydelsen kan selv fortrydes.
    assert back["ingredients"][0]["id"] == r["ingredients"][0]["id"]
    again = client.get(f"/api/recipes/{r['id']}/versions").json()
    assert len(again) == 2 and again[0]["title"] == "Sovs 2"


def test_versions_are_only_for_the_owner_family(client, other):
    r = recipe(client)
    edit(client, r, title="Ny titel")
    vid = client.get(f"/api/recipes/{r['id']}/versions").json()[0]["id"]
    assert other.get(f"/api/recipes/{r['id']}/versions").status_code == 404
    assert other.post(f"/api/recipes/{r['id']}/versions/{vid}/restore").status_code == 404
    assert client.post(f"/api/recipes/{r['id']}/versions/99999/restore").status_code == 404


def test_only_the_newest_versions_are_kept(client):
    r = recipe(client)
    for i in range(35):
        r = edit(client, r, title=f"Sovs {i}")
    assert len(client.get(f"/api/recipes/{r['id']}/versions").json()) == 30


def test_restore_survives_a_deleted_catalog_item(app, client):
    make_system_admin(app)
    r = recipe(client)
    edit(client, r, title="Sovs 2")
    admin = TestClient(app)
    admin.post("/api/admin/login", json={"username": "max", "password": PASSWORD})
    cat = admin.get("/api/admin/ingredients").json()["items"]
    free = next(i for i in cat if i["name"] == "hakket oksekød")
    # Slet varen midt i (først fjernes linjerne, der bruger den, ved at rette opskriften).
    edit(client, client.get(f"/api/recipes/{r['id']}").json(), ingredients=[])
    assert admin.delete(f"/api/admin/ingredients/{free['id']}").status_code == 204
    vid = client.get(f"/api/recipes/{r['id']}/versions").json()[-1]["id"]
    back = client.post(f"/api/recipes/{r['id']}/versions/{vid}/restore")
    assert back.status_code == 200 and len(back.json()["ingredients"]) == 2


def test_catalog_changes_are_listed_and_can_be_undone(app, client):
    make_system_admin(app)
    admin = TestClient(app)
    admin.post("/api/admin/login", json={"username": "max", "password": PASSWORD})
    items = admin.get("/api/admin/ingredients").json()["items"]
    løg = next(i for i in items if i["name"] == "løg")
    # 1) rettelse af en vare
    admin.put(f"/api/admin/ingredients/{løg['id']}", json={"name": "gult løg", "department": løg["department"], "grams_per_piece": 99})
    # 2) nyt alias
    assert admin.post(f"/api/admin/ingredients/{løg['id']}/aliases", json={"alias": "Skalotteløg-ish"}).status_code == 201
    assert admin.post(f"/api/admin/ingredients/{løg['id']}/aliases", json={"alias": "skalotteløg-ish"}).status_code == 409
    # 3) slettet alias
    old = next(a for a in admin.get("/api/admin/ingredients").json()["items"] if a["id"] == løg["id"])["aliases"][0]
    admin.delete(f"/api/admin/aliases/{old['id']}")
    changes = admin.get("/api/admin/changes").json()
    assert [c["summary"].split()[0] for c in changes] == ["Fjernede", "Tilføjede", "Rettede"] and changes[0]["by"] == "max"
    # Fortryd alle tre (nyeste først).
    for c in changes:
        assert admin.post(f"/api/admin/changes/{c['id']}/undo").status_code == 200
    now = next(a for a in admin.get("/api/admin/ingredients").json()["items"] if a["id"] == løg["id"])
    assert now["name"] == "løg" and now["grams_per_piece"] == løg["grams_per_piece"]
    assert old["alias"] in [a["alias"] for a in now["aliases"]] and "skalotteløg-ish" not in [a["alias"] for a in now["aliases"]]
    assert admin.post(f"/api/admin/changes/{changes[0]['id']}/undo").status_code == 409        # allerede fortrudt
    assert all(c["undone"] for c in admin.get("/api/admin/changes").json())


def test_undo_of_deleted_ingredient_recreates_it_with_aliases(app, client):
    make_system_admin(app)
    admin = TestClient(app)
    admin.post("/api/admin/login", json={"username": "max", "password": PASSWORD})
    free = next(i for i in admin.get("/api/admin/ingredients").json()["items"] if i["used_in"] == 0 and i["aliases"])
    admin.delete(f"/api/admin/ingredients/{free['id']}")
    change = admin.get("/api/admin/changes").json()[0]
    assert admin.post(f"/api/admin/changes/{change['id']}/undo").status_code == 200
    back = next(i for i in admin.get("/api/admin/ingredients").json()["items"] if i["name"] == free["name"])
    assert sorted(a["alias"] for a in back["aliases"]) == sorted(a["alias"] for a in free["aliases"])


def test_system_admin_edit_in_the_app_is_in_the_history(app, client):
    make_system_admin(app)
    løg = next(i for i in client.get("/api/ingredients").json() if i["name"] == "løg")
    assert client.put(f"/api/ingredients/{løg['id']}", json={"name": "gult løg", "department": løg["department"],
                      "pantry": False, "grams_per_piece": løg["grams_per_piece"], "grams_per_dl": løg["grams_per_dl"]}).status_code == 200
    admin = TestClient(app)
    admin.post("/api/admin/login", json={"username": "max", "password": PASSWORD})
    assert admin.get("/api/admin/changes").json()[0]["summary"] == "Rettede løg til gult løg"
