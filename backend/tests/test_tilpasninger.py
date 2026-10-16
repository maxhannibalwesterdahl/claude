"""Familiens tilpasninger af fælles opskrifter (flere-familier.md §4)."""

import pytest

from conftest import add_user, login


@pytest.fixture
def other(app, client):
    add_user(app, "bea", "Familie B")
    return login(app, "bea")


def sovs(client):
    return client.post("/api/recipes", json={"title": "Kødsovs", "ingredients": [
        {"raw": "500 g hakket oksekød"}, {"raw": "200 g svampe"}, {"raw": "1 dåse tomater"}]}).json()


def week(c, recipe_id):
    plan = c.post("/api/plans", json={"start_date": "2026-10-26"}).json()
    c.put(f"/api/plans/{plan['id']}/slots", json={"date": "2026-10-26", "kind": "opskrift", "recipe_id": recipe_id})
    return plan["id"]


def line(r, text):
    return next(l for l in r["ingredients"] if l["raw"].endswith(text))


def shopping(c, plan_id):
    items = c.get(f"/api/shopping?plan_id={plan_id}&today=2026-10-20").json()["items"]
    return {i["name"]: i for i in items}


def test_skip_and_own_quantity_change_only_the_familys_view(client, other):
    r = sovs(client)
    pid, bid = week(client, r["id"]), week(other, r["id"])
    out = other.put(f"/api/recipes/{r['id']}/adjustments/lines/{line(r, 'svampe')['id']}", json={"skip": True}).json()
    other.put(f"/api/recipes/{r['id']}/adjustments/lines/{line(r, 'oksekød')['id']}", json={"quantity": 600}).json()
    # Den fælles opskrift er uændret, tilpasningen står ved linjen.
    mine = client.get(f"/api/recipes/{r['id']}").json()
    assert line(mine, "svampe")["skipped"] is False and line(mine, "oksekød")["quantity"] == 500
    theirs = other.get(f"/api/recipes/{r['id']}").json()
    assert line(theirs, "svampe")["skipped"] is True and line(theirs, "oksekød")["my_quantity"] == 600
    assert line(theirs, "oksekød")["quantity"] == 500                      # "Vis original"
    # Indkøbslisten: svampe er væk, kød er 600 g — hos Bea. Hos Max uændret.
    b, a = shopping(other, bid), shopping(client, pid)
    assert "champignon" not in b and b["hakket oksekød"]["amounts"][0]["quantity"] == 600
    assert "champignon" in a and a["hakket oksekød"]["amounts"][0]["quantity"] == 500
    # Dagens ingredienser (Planlæg) følger også.
    meal = other.get(f"/api/plans/{bid}").json()["days"][0]["meal"]
    assert [l["item"] for l in meal["lines"]] == ["hakket oksekød", "tomater"] and meal["lines"][0]["quantity"] == 600
    assert len(client.get(f"/api/plans/{pid}").json()["days"][0]["meal"]["lines"]) == 3


def test_adjustment_can_be_cleared_and_replaced(client):
    r = sovs(client)
    lid = line(r, "svampe")["id"]
    client.put(f"/api/recipes/{r['id']}/adjustments/lines/{lid}", json={"skip": True})
    out = client.put(f"/api/recipes/{r['id']}/adjustments/lines/{lid}", json={"quantity": 100}).json()
    assert line(out, "svampe")["skipped"] is False and line(out, "svampe")["my_quantity"] == 100
    out = client.put(f"/api/recipes/{r['id']}/adjustments/lines/{lid}", json={}).json()
    assert line(out, "svampe")["my_quantity"] is None and not line(out, "svampe")["skipped"]
    assert client.put(f"/api/recipes/{r['id']}/adjustments/lines/999999", json={"skip": True}).status_code == 404
    assert client.put(f"/api/recipes/{r['id']}/adjustments/lines/{lid}", json={"quantity": -1}).status_code == 422


def test_extra_line_goes_on_the_shopping_list_and_can_be_removed(client, other):
    r = sovs(client)
    bid, pid = week(other, r["id"]), week(client, r["id"])
    out = other.post(f"/api/recipes/{r['id']}/adjustments/extra", json={"raw": "  2 dåser   majs "}).json()
    [extra] = out["extra_lines"]
    assert extra["raw"] == "2 dåser majs" and extra["quantity"] == 2 and extra["item"] == "majs"
    assert client.get(f"/api/recipes/{r['id']}").json()["extra_lines"] == []
    assert "majs" in shopping(other, bid) and "majs" not in shopping(client, pid)
    assert client.delete(f"/api/recipes/{r['id']}/adjustments/{extra['id']}").status_code == 404     # ikke Maxs
    assert other.delete(f"/api/recipes/{r['id']}/adjustments/{extra['id']}").json()["extra_lines"] == []
    assert "majs" not in shopping(other, bid)
    assert other.post(f"/api/recipes/{r['id']}/adjustments/extra", json={"raw": "   "}).status_code in (422,)


def test_own_note_is_private_and_clearable(client, other):
    r = sovs(client)
    assert other.put(f"/api/recipes/{r['id']}/adjustments/note", json={"text": " Vi bruger halv chili "}).json()["own_note"] == "Vi bruger halv chili"
    assert client.get(f"/api/recipes/{r['id']}").json()["own_note"] == ""
    assert other.put(f"/api/recipes/{r['id']}/adjustments/note", json={"text": ""}).json()["own_note"] == ""


def test_adjustments_follow_the_recipe_when_it_is_deleted_or_family_erased(app, client, other):
    r = sovs(client)
    other.post(f"/api/recipes/{r['id']}/adjustments/extra", json={"raw": "1 dåse majs"})
    assert client.delete(f"/api/recipes/{r['id']}").status_code == 409          # Bea har den i sin samling nu
    other.delete(f"/api/recipes/{r['id']}/collection")
    assert client.delete(f"/api/recipes/{r['id']}").status_code == 204
    with app.state.db.sessionmaker() as s:
        from madplan.models import HouseholdRecipeAdjustment
        assert s.query(HouseholdRecipeAdjustment).count() == 0


def test_adjusting_puts_recipe_in_the_collection(client, other):
    r = sovs(client)
    assert [x["title"] for x in other.get("/api/recipes").json()] == []
    other.post(f"/api/recipes/{r['id']}/adjustments/extra", json={"raw": "1 dåse majs"})
    assert [x["title"] for x in other.get("/api/recipes").json()] == ["Kødsovs"]


def test_extra_line_in_the_meal_can_be_ticked_as_home(client, other):
    r = sovs(client)
    bid = week(other, r["id"])
    other.post(f"/api/recipes/{r['id']}/adjustments/extra", json={"raw": "2 dåser majs"})
    meal = other.get(f"/api/plans/{bid}").json()["days"][0]["meal"]
    extra = next(l for l in meal["lines"] if l["item"] == "majs")
    assert extra["line_id"] < 0 and extra["group"] == "Jeres ekstra" and extra["quantity"] == 2 and extra["state"] is None
    # Har hjemme på dagen: væk fra indkøbslisten og tilbage igen.
    out = other.put(f"/api/meals/{meal['id']}/lines/{extra['line_id']}", json={"state": "hjemme"}).json()
    assert next(l for l in out["days"][0]["meal"]["lines"] if l["item"] == "majs")["state"] == "hjemme"
    assert "majs" not in shopping(other, bid)
    other.put(f"/api/meals/{meal['id']}/lines/{extra['line_id']}", json={"state": None})
    assert "majs" in shopping(other, bid)
    # Fra indkøbslisten: "har hjemme" på varen markerer også den ekstra linje.
    key = shopping(other, bid)["majs"]["key"]
    other.post("/api/shopping/home", json={"plan_id": bid, "key": key, "home": True})
    assert "majs" not in shopping(other, bid)
    other.post("/api/shopping/home", json={"plan_id": bid, "key": key, "home": False})
    assert "majs" in shopping(other, bid)


def test_extra_line_state_belongs_to_the_familys_own_meal(client, other):
    r = sovs(client)
    aid = week(client, r["id"])
    other.post(f"/api/recipes/{r['id']}/adjustments/extra", json={"raw": "2 dåser majs"})
    meal = client.get(f"/api/plans/{aid}").json()["days"][0]["meal"]
    assert not [l for l in meal["lines"] if l["line_id"] < 0]                       # Maxs dag har ikke Beas ekstra linje
    extra_id = other.get(f"/api/recipes/{r['id']}").json()["extra_lines"][0]["id"]
    assert client.put(f"/api/meals/{meal['id']}/lines/{-extra_id}", json={"state": "hjemme"}).status_code == 404


def test_extra_line_removed_with_its_state(client):
    r = sovs(client)
    pid = week(client, r["id"])
    out = client.post(f"/api/recipes/{r['id']}/adjustments/extra", json={"raw": "2 dåser majs"}).json()
    aid = out["extra_lines"][0]["id"]
    meal = client.get(f"/api/plans/{pid}").json()["days"][0]["meal"]
    client.put(f"/api/meals/{meal['id']}/lines/{-aid}", json={"state": "hjemme"})
    assert client.delete(f"/api/recipes/{r['id']}/adjustments/{aid}").status_code == 200
    assert [l for l in client.get(f"/api/plans/{pid}").json()["days"][0]["meal"]["lines"] if l["line_id"] < 0] == []
