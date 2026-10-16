"""Varekobling pr. familie: rettelser gælder kun familien selv (flere-familier.md §3-4)."""

import pytest
from sqlalchemy import select

from conftest import add_user, ingredient_id, login
from madplan.models import IngredientAlias, RecipeIngredient


@pytest.fixture
def other(app, client):
    add_user(app, "bea", "Familie B")
    return login(app, "bea")


def recipe(c, title, lines):
    return c.post("/api/recipes", json={"title": title, "ingredients": [{"raw": l} for l in lines]}).json()


def first(c, rid):
    return c.get(f"/api/recipes/{rid}").json()["ingredients"][0]


def test_confirm_by_another_family_changes_only_that_familys_view(app, client, other):
    r = recipe(client, "Sovs", ["2 dl fløde"])
    lid = r["ingredients"][0]["id"]
    pisk = ingredient_id(client, "madlavningsfløde")
    out = other.post(f"/api/lines/{lid}/confirm", json={"ingredient_id": pisk}).json()
    assert out == {"also_updated": 0}      # Bea har ikke andre opskrifter med fløde
    assert first(other, r["id"])["ingredient"]["name"] == "madlavningsfløde" and first(other, r["id"])["match_status"] == "bekræftet"
    # Ejerens udgave er uændret, og det fælles katalog og linjen er ikke rørt.
    assert first(client, r["id"])["match_status"] != "bekræftet"
    with app.state.db.sessionmaker() as s:
        line = s.get(RecipeIngredient, lid)
        assert line.match_status == r["ingredients"][0]["match_status"] and line.ingredient_id != pisk
        assert s.scalar(select(IngredientAlias).where(IngredientAlias.key == "fløde", IngredientAlias.source == "user")) is None


def test_preference_follows_the_family_to_new_recipes_and_other_lines(client, other):
    a = recipe(other, "A", ["2 dl fløde"])
    pisk = ingredient_id(other, "madlavningsfløde")
    other.post(f"/api/recipes/{a['id']}/collection")
    b = recipe(other, "B", ["1 dl fløde"])
    other.post(f"/api/lines/{a['ingredients'][0]['id']}/confirm", json={"ingredient_id": pisk})
    # B (samme familie) følger med uden at være bekræftet; nye opskrifter læses med valget.
    assert first(other, b["id"])["ingredient"]["name"] == "madlavningsfløde"
    c = recipe(other, "C", ["3 dl fløde"])
    assert first(other, c["id"])["ingredient"]["name"] == "madlavningsfløde"
    assert other.post("/api/parse", json={"lines": ["1 dl fløde"]}).json()[0]["ingredient"]["name"] == "madlavningsfløde"
    # Max (anden familie) er upåvirket.
    assert client.post("/api/parse", json={"lines": ["1 dl fløde"]}).json()[0]["ingredient"]["name"] != "madlavningsfløde"


def test_shopping_list_uses_the_familys_choice(client, other):
    r = recipe(client, "Sovs", ["2 dl fløde"])
    lid = r["ingredients"][0]["id"]
    for c in (client, other):
        p = c.post("/api/plans", json={"start_date": "2026-10-26"}).json()
        c.put(f"/api/plans/{p['id']}/slots", json={"date": "2026-10-26", "kind": "opskrift", "recipe_id": r["id"]})
    other.post(f"/api/lines/{lid}/confirm", json={"ingredient_id": ingredient_id(other, "madlavningsfløde")})
    names = lambda c: sorted(i["name"] for i in c.get("/api/shopping?today=2026-10-20").json()["items"])   # noqa: E731
    assert names(other) == ["madlavningsfløde"] and names(client) != ["madlavningsfløde"]


def test_ignore_is_per_family_and_review_follows(client, other):
    r = recipe(client, "Suppe", ["1 knivspids zzzxqy"])
    lid = r["ingredients"][0]["id"]
    other.post(f"/api/recipes/{r['id']}/collection")
    assert [l["item"] for l in client.get("/api/review").json()] == ["zzzxqy"]
    assert [l["item"] for l in other.get("/api/review").json()] == ["zzzxqy"]       # Bea har den i sin samling
    assert other.post(f"/api/lines/{lid}/ignore").status_code == 200
    assert other.get("/api/review").json() == [] and len(client.get("/api/review").json()) == 1
    assert first(other, r["id"])["ingredient"] is None and first(other, r["id"])["match_status"] == "bekræftet"


def test_review_only_lists_recipes_in_the_collection(client, other):
    recipe(client, "Suppe", ["1 knivspids zzzxqy"])
    assert other.get("/api/review").json() == []


def test_owner_editing_keeps_a_per_line_choice_and_does_not_leak(client, other):
    r = recipe(client, "A", ["2 dl fløde"])
    pisk = ingredient_id(client, "madlavningsfløde")
    lid = r["ingredients"][0]["id"]
    client.post(f"/api/lines/{lid}/confirm", json={"ingredient_id": pisk})
    rec = client.get(f"/api/recipes/{r['id']}").json()
    body = {"title": "A2", "ingredients": [
        {k: v for k, v in l.items() if k not in ("ingredient", "skipped", "my_quantity")} | {"ingredient_id": l["ingredient"]["id"]}
        for l in rec["ingredients"]]}
    assert client.put(f"/api/recipes/{r['id']}", json=body).status_code == 200
    assert first(client, r["id"])["ingredient"]["name"] == "madlavningsfløde"
    assert first(other, r["id"])["ingredient"]["name"] != "madlavningsfløde"      # ejerens valg lå kun i ejerens lag
