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
