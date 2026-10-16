"""Mærker og tid (docs/flere-familier.md): tid hører til den fælles opskrift,
mærker er den enkelte families egne."""

import json

import pytest

from conftest import add_user, login
from madplan import importer


@pytest.fixture
def other(app, client):
    add_user(app, "bea", "Familie B")
    return login(app, "bea")


def make(client, title="Hakkebøf", **kw):
    return client.post("/api/recipes", json={"title": title, "ingredients": [{"raw": "500 g hakket oksekød"}], **kw}).json()


def tags_of(client, recipe_id):
    return client.get(f"/api/recipes/{recipe_id}").json()["tags"]


def test_tags_belong_to_the_household_that_set_them(client, other):
    r = make(client)
    other.post(f"/api/recipes/{r['id']}/collection")
    client.put(f"/api/recipes/{r['id']}/tags", json={"tags": ["hurtig", "vegetar"]})
    other.put(f"/api/recipes/{r['id']}/tags", json={"tags": ["weekend"]})
    assert tags_of(client, r["id"]) == ["hurtig", "vegetar"]
    assert tags_of(other, r["id"]) == ["weekend"]
    assert [x["tags"] for x in client.get("/api/recipes").json()] == [["hurtig", "vegetar"]]
    assert [x["tags"] for x in other.get("/api/recipes").json()] == [["weekend"]]
    assert [(t["tag"], t["count"]) for t in client.get("/api/tags").json()] == [("hurtig", 1), ("vegetar", 1)]
    assert [(t["tag"], t["count"]) for t in other.get("/api/tags").json()] == [("weekend", 1)]


def test_tags_are_normalized_and_replaced(client):
    r = make(client)
    out = client.put(f"/api/recipes/{r['id']}/tags", json={"tags": ["  Hurtig ", "hurtig", "Børne   venlig", "", "  ", "x" * 50]}).json()
    assert out["tags"] == ["børne venlig", "hurtig", "x" * 40]
    # Erstatter de gamle, og tom liste fjerner dem.
    assert client.put(f"/api/recipes/{r['id']}/tags", json={"tags": ["fisk"]}).json()["tags"] == ["fisk"]
    assert client.put(f"/api/recipes/{r['id']}/tags", json={"tags": []}).json()["tags"] == []


def test_at_most_twelve_tags(client):
    r = make(client)
    twelve = [f"mærke {i}" for i in range(12)]
    assert len(client.put(f"/api/recipes/{r['id']}/tags", json={"tags": twelve}).json()["tags"]) == 12
    assert client.put(f"/api/recipes/{r['id']}/tags", json={"tags": twelve + ["for mange"]}).status_code == 422
    # Dubletter tæller ikke med.
    assert client.put(f"/api/recipes/{r['id']}/tags", json={"tags": twelve + ["MÆRKE 1"]}).status_code == 200


def test_tags_need_the_recipe_in_collection_or_owned(client, other):
    r = make(client)
    assert other.put(f"/api/recipes/{r['id']}/tags", json={"tags": ["hurtig"]}).status_code == 404
    assert other.get("/api/tags").json() == []
    assert other.put("/api/recipes/9999/tags", json={"tags": []}).status_code == 404


def test_tag_counts_are_sorted_by_count_then_name(client):
    a = make(client, "A")
    b = make(client, "B")
    client.put(f"/api/recipes/{a['id']}/tags", json={"tags": ["vegetar", "hurtig"]})
    client.put(f"/api/recipes/{b['id']}/tags", json={"tags": ["hurtig", "fisk"]})
    assert [(t["tag"], t["count"]) for t in client.get("/api/tags").json()] == [
        ("hurtig", 2), ("fisk", 1), ("vegetar", 1)]


def test_removing_from_collection_drops_the_tags(client, other):
    r = make(client)
    other.post(f"/api/recipes/{r['id']}/collection")
    other.put(f"/api/recipes/{r['id']}/tags", json={"tags": ["hurtig"]})
    client.put(f"/api/recipes/{r['id']}/tags", json={"tags": ["fisk"]})
    assert other.delete(f"/api/recipes/{r['id']}/collection").json()["tags"] == []
    assert other.get("/api/tags").json() == []
    # Det er kun den ene familie, der mister sine mærker.
    assert tags_of(client, r["id"]) == ["fisk"]
    # Lægges den i samlingen igen, er den uden mærker.
    other.post(f"/api/recipes/{r['id']}/collection")
    assert tags_of(other, r["id"]) == []


def test_owner_sets_total_minutes(client, other):
    r = make(client, total_minutes=35)
    assert r["total_minutes"] == 35
    out = client.put(f"/api/recipes/{r['id']}", json={"title": "Hakkebøf", "total_minutes": 50,
                                                     "ingredients": [{"raw": "500 g hakket oksekød"}]}).json()
    assert out["total_minutes"] == 50
    # Familie B ejer den ikke og kan ikke ændre tiden.
    assert other.put(f"/api/recipes/{r['id']}", json={"title": "Hakkebøf", "total_minutes": 5}).status_code == 404
    assert client.get(f"/api/recipes/{r['id']}").json()["total_minutes"] == 50
    assert other.get(f"/api/recipes/{r['id']}").json()["total_minutes"] == 50


def test_total_minutes_is_optional_and_bounded(client):
    r = make(client)
    assert r["total_minutes"] is None
    assert make(client, "Lang", total_minutes=1440)["total_minutes"] == 1440
    assert client.post("/api/recipes", json={"title": "X", "total_minutes": 0}).status_code == 422
    assert client.post("/api/recipes", json={"title": "X", "total_minutes": 1441}).status_code == 422


def test_list_shows_minutes_for_own_collection(client, other):
    r = make(client, total_minutes=20)
    other.post(f"/api/recipes/{r['id']}/collection")
    row = other.get("/api/recipes").json()[0]
    assert row["total_minutes"] == 20 and row["tags"] == []


def test_export_includes_tags_and_time(client):
    r = make(client, total_minutes=25)
    client.put(f"/api/recipes/{r['id']}/tags", json={"tags": ["hurtig"]})
    data = client.get("/api/household/export").json()
    assert data["tags"] == [{"recipe_id": r["id"], "tag": "hurtig"}]
    assert data["recipes_owned"][0]["total_minutes"] == 25


def _page(ld: dict) -> str:
    return ('<html><head><script type="application/ld+json">'
            + json.dumps({"@context": "https://schema.org", "@type": "Recipe", "name": "Pasta",
                          "recipeIngredient": ["200 g pasta"], "recipeInstructions": ["Kog pastaen"], **ld})
            + "</script></head><body></body></html>")


@pytest.mark.parametrize("ld,expected", [
    ({"totalTime": "PT35M"}, 35),
    ({"totalTime": "PT1H15M"}, 75),
    ({"prepTime": "PT10M", "cookTime": "PT25M"}, 35),
    ({"totalTime": "PT0M"}, None),
    ({}, None),
])
def test_import_reads_total_time(ld, expected):
    r = importer.scrape(_page(ld), "https://www.example.dk/pasta")
    assert r.total_minutes == expected


def test_nemlig_import_has_no_time():
    page = json.dumps({"content": [{"TemplateName": "recipedetailspot", "Header": "Lasagne",
                                    "IngredientGroups": [{"Name": "", "Ingredients": [{"Text": "Mælk", "Amount": "1", "Unit": "l"}]}]}]})
    r = importer.scrape_nemlig(page, "https://www.nemlig.com/opskrifter/lasagne")
    assert r.total_minutes is None
