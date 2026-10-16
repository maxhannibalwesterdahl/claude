import pytest

from conftest import add_user, login

START = "2026-10-04"  # søndag
TODAY = "2026-10-04"


@pytest.fixture
def make(client):
    def make(title, lines=None):
        body = {"title": title, "servings": 4}
        if lines is not None:
            body["ingredients"] = [{"raw": l} for l in lines]
        r = client.post("/api/recipes", json=body)
        assert r.status_code == 201, r.text
        return r.json()
    return make


@pytest.fixture
def recipes(make):
    return {"kødsovs": make("Kødsovs"), "lasagne": make("Lasagne"), "suppe": make("Suppe")}


def new_plan(client, start=START, days=7):
    r = client.post("/api/plans", json={"start_date": start, "days": days})
    assert r.status_code == 201, r.text
    return r.json()


def put(client, plan, **slot):
    r = client.put(f"/api/plans/{plan['id']}/slots", json=slot)
    assert r.status_code == 200, r.text
    return r.json()


def set_mains(client, recipe, items):
    """Sæt hovedingredienser på de linjer, hvis vare står i `items`."""
    rec = client.get(f"/api/recipes/{recipe['id']}").json()
    for line in rec["ingredients"]:
        r = client.put(f"/api/lines/{line['id']}/main", json={"is_main": line["item"] in items})
        assert r.status_code == 200, r.text


def fill(client, plan, today=TODAY):
    r = client.get(f"/api/plans/{plan['id']}/fill", params={"today": today})
    assert r.status_code == 200, r.text
    return r.json()


def titles(days):
    return [(d["date"], d["recipe"]["title"], d["reason"]) for d in days]


def test_requires_login(anon):
    assert anon.get("/api/plans/1/fill").status_code == 401


def test_empty_collection_gives_no_days(client):
    plan = new_plan(client)
    out = fill(client, plan)
    assert out["days"] == [] and out["alternatives"] == []


def test_wishes_come_first_in_wishlist_order(client, recipes):
    plan = new_plan(client)
    client.put(f"/api/recipes/{recipes['lasagne']['id']}/favorite", json={"favorite": True})
    client.post(f"/api/plans/{plan['id']}/wishlist", json={"recipe_id": recipes["suppe"]["id"]})
    client.post(f"/api/plans/{plan['id']}/wishlist", json={"recipe_id": recipes["kødsovs"]["id"]})
    days = fill(client, plan)["days"]
    assert titles(days)[:3] == [("2026-10-04", "Suppe", "ønske"), ("2026-10-05", "Kødsovs", "ønske"),
                                ("2026-10-06", "Lasagne", "favorit")]


def test_favorites_before_others(client, recipes, make):
    plan = new_plan(client, days=2)
    client.put(f"/api/recipes/{recipes['suppe']['id']}/favorite", json={"favorite": True})
    days = fill(client, plan)["days"]
    assert titles(days) == [("2026-10-04", "Suppe", "favorit"), ("2026-10-05", "Kødsovs", "længe siden")]


def test_favorites_ordered_longest_since_planned(client, recipes):
    old = new_plan(client, "2026-09-20", days=14)
    put(client, old, date="2026-09-21", kind="opskrift", recipe_id=recipes["suppe"]["id"])
    put(client, old, date="2026-09-26", kind="opskrift", recipe_id=recipes["kødsovs"]["id"])
    for key in ("kødsovs", "suppe"):
        client.put(f"/api/recipes/{recipes[key]['id']}/favorite", json={"favorite": True})
    plan = new_plan(client, "2026-10-12", days=3)
    days = fill(client, plan, today="2026-10-12")["days"]
    # Suppe har længst siden, og Lasagne er ikke favorit, så den kommer sidst.
    assert titles(days) == [("2026-10-12", "Suppe", "favorit"), ("2026-10-13", "Kødsovs", "favorit"),
                            ("2026-10-14", "Lasagne", "længe siden")]


def test_past_and_filled_days_are_skipped(client, recipes):
    plan = new_plan(client)
    put(client, plan, date="2026-10-07", kind="fritekst", text="Pizza")
    put(client, plan, date="2026-10-09", for_child=True, kind="fritekst", text="Pasta")
    days = fill(client, plan, today="2026-10-06")["days"]
    assert [d["date"] for d in days] == ["2026-10-06", "2026-10-08", "2026-10-10"]


@pytest.fixture
def meat(client, make):
    """Tre retter med hovedingredienser: to med hakket oksekød, en med gulerødder."""
    out = {
        "kødsovs": make("Kødsovs", ["500 g hakket oksekød", "2 løg"]),
        "lasagne": make("Lasagne", ["500 g hakket oksekød", "9 lasagneplader"]),
        "suppe": make("Suppe", ["3 gulerødder", "1 porre"]),
    }
    set_mains(client, out["kødsovs"], {"hakket oksekød"})
    set_mains(client, out["lasagne"], {"hakket oksekød"})
    set_mains(client, out["suppe"], {"gulerødder"})
    return out


def test_no_shared_main_ingredient(client, meat):
    plan = new_plan(client, days=2)
    assert [d["recipe"]["title"] for d in fill(client, plan)["days"]] == ["Kødsovs", "Suppe"]


def test_main_ingredient_on_plan_counts(client, meat):
    plan = new_plan(client)
    put(client, plan, date="2026-10-10", kind="opskrift", recipe_id=meat["kødsovs"]["id"])
    days = fill(client, plan)["days"]
    # Kødsovs står på planen, så Lasagne (samme kød) må ikke komme først.
    assert titles(days)[0] == ("2026-10-04", "Suppe", "længe siden")


def test_repeats_when_nothing_else_fits(client, recipes):
    plan = new_plan(client, days=2)
    client.delete(f"/api/recipes/{recipes['lasagne']['id']}")
    client.delete(f"/api/recipes/{recipes['suppe']['id']}")
    days = fill(client, plan)["days"]
    assert [d["recipe"]["title"] for d in days] == ["Kødsovs", "Kødsovs"]


def test_recently_planned_are_skipped(client, recipes):
    old = new_plan(client, "2026-09-20", days=14)
    put(client, old, date="2026-10-01", kind="opskrift", recipe_id=recipes["suppe"]["id"])
    client.put(f"/api/recipes/{recipes['lasagne']['id']}/favorite", json={"favorite": True})
    client.put(f"/api/recipes/{recipes['suppe']['id']}/favorite", json={"favorite": True})
    plan = new_plan(client, START, days=7)
    names = {d["recipe"]["title"] for d in fill(client, plan)["days"]}
    assert "Suppe" not in names and {"Kødsovs", "Lasagne"} <= names


def test_wish_is_not_blocked_by_recent_planning(client, recipes):
    old = new_plan(client, "2026-09-20", days=14)
    put(client, old, date="2026-10-01", kind="opskrift", recipe_id=recipes["suppe"]["id"])
    plan = new_plan(client, START, days=7)
    client.post(f"/api/plans/{plan['id']}/wishlist", json={"recipe_id": recipes["suppe"]["id"]})
    assert titles(fill(client, plan)["days"])[0] == ("2026-10-04", "Suppe", "ønske")


def test_recipes_already_on_plan_are_not_proposed(client, recipes):
    plan = new_plan(client, days=3)
    put(client, plan, date="2026-10-06", kind="opskrift", recipe_id=recipes["suppe"]["id"])
    names = [d["recipe"]["title"] for d in fill(client, plan)["days"]]
    assert "Suppe" not in names and len(names) == 2


def test_alternatives_do_not_overlap_days(client, make):
    for i in range(20):
        make(f"Ret {i:02d}")
    plan = new_plan(client)
    out = fill(client, plan)
    day_ids = {d["recipe"]["id"] for d in out["days"]}
    alt_ids = [a["id"] for a in out["alternatives"]]
    assert len(out["days"]) == 7 and len(alt_ids) == 12
    assert day_ids.isdisjoint(alt_ids)


def test_alternatives_are_the_rest_in_order(client, recipes):
    plan = new_plan(client, days=2)
    out = fill(client, plan)
    assert [a["title"] for a in out["alternatives"]] == ["Suppe"]


def test_other_household_is_404(client, app, recipes):
    plan = new_plan(client)
    add_user(app, "anna", "Familie B")
    other = login(app, "anna")
    assert other.get(f"/api/plans/{plan['id']}/fill").status_code == 404
    assert other.post(f"/api/plans/{plan['id']}/fill", json={"days": []}).status_code == 404


def test_get_saves_nothing(client, recipes):
    plan = new_plan(client)
    fill(client, plan)
    current = client.get(f"/api/plans/{plan['id']}").json()
    assert all(d["meal"] is None and d["child"] is None for d in current["days"])


def test_post_places_days_and_removes_wishes(client, recipes):
    plan = new_plan(client)
    client.post(f"/api/plans/{plan['id']}/wishlist", json={"recipe_id": recipes["suppe"]["id"]})
    r = client.post(f"/api/plans/{plan['id']}/fill", params={"today": TODAY}, json={"days": [
        {"date": "2026-10-04", "recipe_id": recipes["suppe"]["id"]},
        {"date": "2026-10-05", "recipe_id": recipes["lasagne"]["id"]},
    ]})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["days"][0]["meal"]["title"] == "Suppe" and out["days"][1]["meal"]["title"] == "Lasagne"
    assert out["wishlist"] == []


def test_post_skips_filled_and_past_days(client, recipes):
    plan = new_plan(client)
    put(client, plan, date="2026-10-04", kind="fritekst", text="Pizza")
    r = client.post(f"/api/plans/{plan['id']}/fill", params={"today": "2026-10-05"}, json={"days": [
        {"date": "2026-10-04", "recipe_id": recipes["suppe"]["id"]},
        {"date": "2026-10-05", "recipe_id": recipes["suppe"]["id"]},
    ]})
    out = r.json()
    assert out["days"][0]["meal"]["title"] == "Pizza"
    assert out["days"][1]["meal"]["title"] == "Suppe"


def test_post_outside_plan_is_422(client, recipes):
    plan = new_plan(client)
    r = client.post(f"/api/plans/{plan['id']}/fill", json={"days": [
        {"date": "2026-12-01", "recipe_id": recipes["suppe"]["id"]}]})
    assert r.status_code == 422


def test_post_other_household_is_404(client, app, recipes):
    plan = new_plan(client)
    add_user(app, "anna", "Familie B")
    other = login(app, "anna")
    r = other.post(f"/api/plans/{plan['id']}/fill", json={"days": [
        {"date": "2026-10-04", "recipe_id": recipes["suppe"]["id"]}]})
    assert r.status_code == 404
    assert client.get(f"/api/plans/{plan['id']}").json()["days"][0]["meal"] is None
