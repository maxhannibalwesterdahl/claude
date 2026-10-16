"""Vores samling og familiens egen note (flere-familier.md §1, §4, §7)."""

import pytest

from conftest import add_user, login


@pytest.fixture
def other(app, client):
    add_user(app, "bea", "Familie B")
    return login(app, "bea")


def make(client, title="Hakkebøf", **kw):
    return client.post("/api/recipes", json={"title": title, "ingredients": [{"raw": "500 g hakket oksekød"}], **kw}).json()


def titles(c, **params):
    return [r["title"] for r in c.get("/api/recipes", params=params).json()]


def test_own_recipes_are_in_own_collection_only(client, other):
    r = make(client)
    assert r["in_collection"] and titles(client) == ["Hakkebøf"]
    assert titles(other) == [] and titles(other, alle="true") == ["Hakkebøf"]
    row = other.get("/api/recipes", params={"alle": "true"}).json()[0]
    assert (row["in_collection"], row["owned"]) == (False, False)


def test_add_and_remove_from_collection(client, other):
    r = make(client)
    out = other.post(f"/api/recipes/{r['id']}/collection").json()
    assert out["in_collection"] and not out["owned"]
    assert titles(other) == ["Hakkebøf"]
    # Idempotent, og fjernes kun for den ene familie.
    assert other.post(f"/api/recipes/{r['id']}/collection").status_code == 200
    assert not other.delete(f"/api/recipes/{r['id']}/collection").json()["in_collection"]
    assert titles(other) == [] and titles(client) == ["Hakkebøf"]
    assert other.post("/api/recipes/9999/collection").status_code == 404


def test_planning_a_shared_recipe_puts_it_in_the_collection(client, other):
    r = make(client)
    plan = other.post("/api/plans", json={"start_date": "2026-10-26"}).json()
    other.put(f"/api/plans/{plan['id']}/slots", json={"date": "2026-10-26", "kind": "opskrift", "recipe_id": r["id"]})
    assert titles(other) == ["Hakkebøf"]
    # Ønskelisten tæller også.
    r2 = make(client, "Tacos")
    other.post(f"/api/plans/{plan['id']}/wishlist", json={"recipe_id": r2["id"]})
    assert titles(other) == ["Hakkebøf", "Tacos"]


def test_suggestions_come_from_own_collection(client, other):
    make(client, "A's ret")
    assert other.get("/api/suggestions").json() == []
    assert [s["recipe"]["title"] for s in client.get("/api/suggestions").json()] == ["A's ret"]


def test_favorite_is_per_family(client, other):
    r = make(client)
    assert client.put(f"/api/recipes/{r['id']}/favorite", json={"favorite": True}).json()["favorite"]
    assert not other.get(f"/api/recipes/{r['id']}").json()["favorite"]
    assert other.put(f"/api/recipes/{r['id']}/favorite", json={"favorite": True}).json()["in_collection"]
    assert [x["favorite"] for x in client.get("/api/recipes").json()] == [True]


def test_other_family_can_write_its_own_note_without_touching_the_recipe(client, other):
    r = make(client, child_note="uden chili")
    out = other.put(f"/api/recipes/{r['id']}/note", json={"child_note": "  halv portion "}).json()
    assert out["child_note"] == "halv portion" and out["title"] == "Hakkebøf"
    assert client.get(f"/api/recipes/{r['id']}").json()["child_note"] == "uden chili"
    assert other.get(f"/api/recipes/{r['id']}").json()["child_note"] == "halv portion"
    assert other.put(f"/api/recipes/{r['id']}/note", json={"child_note": "x" * 2001}).status_code == 422


def test_owner_cannot_delete_recipe_in_another_families_collection(client, other):
    r = make(client)
    other.post(f"/api/recipes/{r['id']}/collection")
    assert client.delete(f"/api/recipes/{r['id']}").status_code == 409
    other.delete(f"/api/recipes/{r['id']}/collection")
    assert client.delete(f"/api/recipes/{r['id']}").status_code == 204


def test_importing_the_same_link_again_reuses_the_recipe(client, other):
    r = make(client, source_url="https://www.valdemarsro.dk/hakkeboef/")
    res = other.post("/api/recipes/import", json={"url": "https://www.valdemarsro.dk/hakkeboef"})
    assert res.status_code == 409 and res.json()["detail"]["id"] == r["id"]
    assert titles(other) == ["Hakkebøf"]
