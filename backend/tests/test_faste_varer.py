"""Faste varer: varer, familien køber hver uge (kommer på hver uges indkøbsliste)."""

import pytest
from conftest import add_user, ingredient_id, login

from madplan.shopping import Amount, cover

START = "2026-10-04"


# --- cover: den største mængde tæller ------------------------------------------------

@pytest.mark.parametrize("fixed, need, gpp, gpd, expected", [
    ([(2, "l")], [(1, "l")], None, None, [Amount(2, "l")]),
    ([(2, "l")], [(3, "l")], None, None, [Amount(3, "l")]),
    ([(2, "l")], [(5, "dl")], None, None, [Amount(2, "l")]),
    ([(1, "pakke")], [(500, "g")], None, None, [Amount(1, "pakke"), Amount(500, "g")]),
    ([(6, None)], [(4, None)], None, None, [Amount(6, None)]),
    ([(2, "dl")], [(500, "g")], None, 100, [Amount(500, "g")]),
    ([(2, "dl")], [(100, "g")], None, 100, [Amount(2, "dl")]),
    ([(1, None)], [(300, "g")], 150, None, [Amount(300, "g")]),
    ([], [(3, "l")], None, None, [Amount(3, "l")]),
    ([(2, "l")], [], None, None, [Amount(2, "l")]),
    ([], [], None, None, []),
])
def test_cover_takes_the_larger_amount(fixed, need, gpp, gpd, expected):
    assert cover(fixed, need, gpp, gpd) == expected


# --- API ------------------------------------------------------------------------------

def by_key(data):
    return {i["key"]: i for i in data["items"]}


def fmt(item):
    return [(a["quantity"], a["unit"]) for a in item["amounts"]]


def plan_with(client, lines, start=START, title="Ret"):
    recipe = client.post("/api/recipes", json={"title": title, "ingredients": [{"raw": l} for l in lines]}).json()
    plan = client.post("/api/plans", json={"start_date": start}).json()
    client.put(f"/api/plans/{plan['id']}/slots",
               json={"date": start, "kind": "opskrift", "recipe_id": recipe["id"], "multiplier": 1})
    return plan


def test_staple_crud(client):
    res = client.post("/api/staples", json={"text": "  2 l   mælk "})
    assert res.status_code == 201
    s = res.json()
    assert (s["text"], s["quantity"], s["unit"], s["item"]) == ("2 l mælk", 2, "l", "mælk")
    assert s["ingredient_id"] == ingredient_id(client, "mælk") and s["department"] == "mej"

    # Ny tekst læses igen
    s = client.patch(f"/api/staples/{s['id']}", json={"text": "1 pk kaffe"}).json()
    assert (s["item"], s["unit"], s["quantity"]) == ("kaffe", "pakke", 1)

    # Vare fjernes igen: den kommer under "Andet"
    s = client.patch(f"/api/staples/{s['id']}", json={"ingredient_id": None}).json()
    assert s["ingredient_id"] is None and s["department"] == "andet"
    assert [x["text"] for x in client.get("/api/staples").json()] == ["1 pk kaffe"]

    assert client.post("/api/staples", json={"text": " "}).status_code == 422
    assert client.delete(f"/api/staples/{s['id']}").status_code == 204
    assert client.get("/api/staples").json() == []


def test_other_household_gets_404(app, client):
    s = client.post("/api/staples", json={"text": "2 l mælk"}).json()
    add_user(app, "bea", "Familie B")
    bea = login(app, "bea")
    assert bea.get("/api/staples").json() == []
    assert bea.patch(f"/api/staples/{s['id']}", json={"text": "1 l mælk"}).status_code == 404
    assert bea.delete(f"/api/staples/{s['id']}").status_code == 404


def test_staple_without_plan_is_not_shown(client):
    client.post("/api/staples", json={"text": "2 l mælk"})
    assert client.get("/api/shopping").json()["items"] == []


def test_staple_is_on_the_list_every_week(client):
    s = client.post("/api/staples", json={"text": "2 l mælk"}).json()
    plan = client.post("/api/plans", json={"start_date": START}).json()
    data = client.get(f"/api/shopping?plan_id={plan['id']}").json()
    item = by_key(data)[f"i:{s['ingredient_id']}"]
    assert item["kind"] == "staple" and item["staple"] == "2 l mælk"
    assert fmt(item) == [(2, "l")] and not item["unknown"]


def test_staple_and_recipe_use_the_larger_amount(client):
    s = client.post("/api/staples", json={"text": "2 l mælk"}).json()
    key = f"i:{s['ingredient_id']}"
    cases = [
        (["1 l mælk"], "2026-10-04", [(2, "l")]),       # faste 2 l dækker 1 l
        (["3 l mælk"], "2026-10-11", [(3, "l")]),       # retterne kræver 3 l
        (["5 dl mælk"], "2026-10-18", [(2, "l")]),      # 2 l er mere end 5 dl
    ]
    for i, (lines, start, expected) in enumerate(cases):
        plan = plan_with(client, lines, start, title=f"Ret {i}")
        data = client.get(f"/api/shopping?plan_id={plan['id']}").json()
        item = by_key(data)[key]
        assert item["kind"] == "plan" and item["staple"] == "2 l mælk"
        assert fmt(item) == expected


def test_staple_stays_when_recipes_are_at_home(client):
    s = client.post("/api/staples", json={"text": "2 l mælk"}).json()
    key = f"i:{s['ingredient_id']}"
    plan = plan_with(client, ["1 l mælk"])
    client.post("/api/shopping/home", json={"plan_id": plan["id"], "key": key, "home": True})
    data = client.get(f"/api/shopping?plan_id={plan['id']}").json()
    assert fmt(by_key(data)[key]) == [(2, "l")]
    assert key not in [h["key"] for h in data["home"]]


def test_unknown_staple_can_be_checked_off(client):
    s = client.post("/api/staples", json={"text": "3 zibbelstykker"}).json()
    assert s["ingredient_id"] is None
    plan = client.post("/api/plans", json={"start_date": START}).json()
    key = f"f:{s['id']}"
    item = by_key(client.get(f"/api/shopping?plan_id={plan['id']}").json())[key]
    assert item["kind"] == "staple" and item["unknown"] and not item["checked"]

    change = {"key": key, "checked": True, "ts": 10**13}
    data = client.post("/api/shopping/sync", json={"plan_id": plan["id"], "view_plan_id": plan["id"],
                                                   "changes": [change]}).json()
    assert by_key(data)[key]["checked"]


def test_export_contains_staples(client):
    client.post("/api/staples", json={"text": "2 l mælk"})
    d = client.get("/api/household/export").json()
    assert d["staples"] == [{"text": "2 l mælk", "quantity": 2, "unit": "l"}]
