from datetime import date

import pytest

from madplan.planning import scale

START = "2026-10-04"  # søndag


@pytest.fixture
def recipes(client):
    def make(title, lines):
        return client.post("/api/recipes", json={"title": title, "servings": 4,
                                                 "ingredients": [{"raw": l} for l in lines]}).json()
    return {
        "kødsovs": make("Kødsovs", ["500 g hakket oksekød", "2 løg", "1 dåse hakkede tomater", "salt og peber"]),
        "lasagne": make("Lasagne", ["500 g hakket oksekød", "1 dåse hakkede tomater", "9 lasagneplader", "3 dl mælk"]),
        "suppe": make("Suppe", ["3 gulerødder", "1 porre", "½ dåse kokosmælk"]),
    }


@pytest.fixture
def plan(client):
    r = client.post("/api/plans", json={"start_date": START})
    assert r.status_code == 201, r.text
    return r.json()


def day(plan, d):
    return next(x for x in plan["days"] if x["date"] == d)


def put(client, plan, **slot):
    r = client.put(f"/api/plans/{plan['id']}/slots", json=slot)
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.parametrize("q, unit, m, expected", [
    (500, "g", 0.5, 250), (1, "dåse", 0.5, 1), (3, None, 0.5, 2), (0.5, "dåse", 2, 1),
    (2, "dl", 0.5, 1), (1, "fed", 0.5, 1), (None, None, 2, None), (1.5, "spsk", 2, 3),
])
def test_scale(q, unit, m, expected):
    assert scale(q, unit, m) == expected


def test_new_plan_has_seven_empty_days(plan):
    assert plan["start_date"] == START and plan["end_date"] == "2026-10-10"
    assert [d["date"] for d in plan["days"]][:2] == ["2026-10-04", "2026-10-05"]
    assert all(d["meal"] is None and d["child"] is None for d in plan["days"])


def test_overlapping_plan_is_rejected(client, plan):
    r = client.post("/api/plans", json={"start_date": "2026-10-08"})
    assert r.status_code == 409 and r.json()["detail"]["id"] == plan["id"]
    assert client.post("/api/plans", json={"start_date": "2026-10-11"}).status_code == 201


def test_current_plan(client, plan):
    assert client.get("/api/plans/current?today=2026-10-06").json()["id"] == plan["id"]
    # Før planen: den kommende. Efter: den seneste.
    assert client.get("/api/plans/current?today=2026-09-01").json()["id"] == plan["id"]
    assert client.get("/api/plans/current?today=2026-12-01").json()["id"] == plan["id"]


def test_no_plan_is_404(client):
    assert client.get("/api/plans/current").status_code == 404


def test_recipe_meal_with_multiplier(client, plan, recipes):
    p = put(client, plan, date=START, kind="opskrift", recipe_id=recipes["suppe"]["id"], multiplier=0.5)
    meal = day(p, START)["meal"]
    assert meal["title"] == "Suppe" and meal["recipe"]["servings"] == 4
    # ×½: 3 gulerødder -> 2 (rundet op), ½ dåse -> 1 dåse
    assert [(l["item"], l["quantity"]) for l in meal["lines"]] == [
        ("gulerødder", 2), ("porre", 1), ("kokosmælk", 1)]

    p = client.patch(f"/api/meals/{meal['id']}", json={"multiplier": 2}).json()
    assert [l["quantity"] for l in day(p, START)["meal"]["lines"]] == [6, 2, 1]
    assert client.patch(f"/api/meals/{meal['id']}", json={"multiplier": 3}).status_code == 422


def test_free_text_and_child_meal(client, plan, recipes):
    put(client, plan, date=START, kind="fritekst", text="Pizza ude")
    p = put(client, plan, date=START, for_child=True, kind="fritekst", text="Grød")
    d = day(p, START)
    assert d["meal"]["title"] == "Pizza ude" and d["meal"]["lines"] == []
    assert d["child"]["title"] == "Grød"
    assert client.put(f"/api/plans/{plan['id']}/slots",
                      json={"date": START, "kind": "fritekst", "text": "  "}).status_code == 422


def test_slot_is_replaced(client, plan, recipes):
    put(client, plan, date=START, kind="fritekst", text="Pizza")
    p = put(client, plan, date=START, kind="opskrift", recipe_id=recipes["suppe"]["id"])
    assert day(p, START)["meal"]["title"] == "Suppe"


def test_date_outside_plan(client, plan):
    r = client.put(f"/api/plans/{plan['id']}/slots", json={"date": "2026-10-11", "kind": "fritekst", "text": "x"})
    assert r.status_code == 422


def test_leftovers_and_uses_leftover(client, plan, recipes):
    p = put(client, plan, date="2026-10-05", kind="opskrift", recipe_id=recipes["kødsovs"]["id"])
    source = day(p, "2026-10-05")["meal"]

    # Rester fra kødsovsen dagen efter: intet indkøb.
    p = put(client, plan, date="2026-10-06", kind="rester", leftover_from_id=source["id"])
    rest = day(p, "2026-10-06")["meal"]
    assert rest["title"] == "Rester: Kødsovs" and rest["lines"] == [] and rest["suggest_double"]

    # Rester skal komme fra en tidligere dag.
    r = client.put(f"/api/plans/{plan['id']}/slots",
                   json={"date": "2026-10-04", "kind": "rester", "leftover_from_id": source["id"]})
    assert r.status_code == 422

    # Lasagne bruger rest fra kødsovsen og dækker kød og tomater.
    p = put(client, plan, date="2026-10-07", kind="opskrift", recipe_id=recipes["lasagne"]["id"])
    las = day(p, "2026-10-07")["meal"]
    first = las["lines"][0]["line_id"]
    assert client.put(f"/api/meals/{las['id']}/lines/{first}", json={"state": "rest"}).status_code == 422
    p = client.patch(f"/api/meals/{las['id']}", json={"leftover_from_id": source["id"]}).json()
    las = day(p, "2026-10-07")["meal"]
    assert las["leftover_from"]["title"] == "Kødsovs" and las["suggest_double"]
    for line in las["lines"][:2]:
        p = client.put(f"/api/meals/{las['id']}/lines/{line['line_id']}", json={"state": "rest"}).json()
    las = day(p, "2026-10-07")["meal"]
    assert [l["state"] for l in las["lines"]] == ["rest", "rest", None, None]

    # Kilden sættes til ×2: forslaget forsvinder, men kilden ændres ikke af sig selv.
    assert day(p, "2026-10-05")["meal"]["multiplier"] == 1
    p = client.patch(f"/api/meals/{source['id']}", json={"multiplier": 2}).json()
    assert not day(p, "2026-10-07")["meal"]["suggest_double"]

    # Fjernes kilden, mister lasagnen koblingen og rest-markeringerne.
    p = client.delete(f"/api/meals/{source['id']}").json()
    las = day(p, "2026-10-07")["meal"]
    assert las["leftover_from"] is None and [l["state"] for l in las["lines"]] == [None] * 4
    assert day(p, "2026-10-06")["meal"]["title"] == "Rester"


def test_line_state_home(client, plan, recipes):
    p = put(client, plan, date=START, kind="opskrift", recipe_id=recipes["suppe"]["id"])
    meal = day(p, START)["meal"]
    line = meal["lines"][1]["line_id"]
    p = client.put(f"/api/meals/{meal['id']}/lines/{line}", json={"state": "hjemme"}).json()
    assert [l["state"] for l in day(p, START)["meal"]["lines"]] == [None, "hjemme", None]
    p = client.put(f"/api/meals/{meal['id']}/lines/{line}", json={"state": None}).json()
    assert [l["state"] for l in day(p, START)["meal"]["lines"]] == [None, None, None]
    other = recipes["lasagne"]["ingredients"][0]["id"]
    assert client.put(f"/api/meals/{meal['id']}/lines/{other}", json={"state": "hjemme"}).status_code == 404


def test_move_swaps_meals(client, plan, recipes):
    put(client, plan, date="2026-10-04", kind="fritekst", text="A")
    p = put(client, plan, date="2026-10-05", kind="fritekst", text="B")
    a = day(p, "2026-10-04")["meal"]
    p = client.post(f"/api/meals/{a['id']}/move", json={"date": "2026-10-05"}).json()
    assert day(p, "2026-10-04")["meal"]["title"] == "B"
    assert day(p, "2026-10-05")["meal"]["title"] == "A"
    # Til en tom plads og til barnets plads.
    p = client.post(f"/api/meals/{a['id']}/move", json={"date": "2026-10-08", "for_child": True}).json()
    assert day(p, "2026-10-05")["meal"] is None and day(p, "2026-10-08")["child"]["title"] == "A"


def test_move_breaks_impossible_leftover(client, plan, recipes):
    p = put(client, plan, date="2026-10-05", kind="opskrift", recipe_id=recipes["kødsovs"]["id"])
    src = day(p, "2026-10-05")["meal"]
    p = put(client, plan, date="2026-10-06", kind="rester", leftover_from_id=src["id"])
    p = client.post(f"/api/meals/{src['id']}/move", json={"date": "2026-10-09"}).json()
    assert day(p, "2026-10-06")["meal"]["leftover_from"] is None


def test_wishlist(client, plan, recipes):
    p = client.post(f"/api/plans/{plan['id']}/wishlist", json={"recipe_id": recipes["suppe"]["id"]}).json()
    p = client.post(f"/api/plans/{plan['id']}/wishlist", json={"text": "Tacos"}).json()
    assert [w["title"] for w in p["wishlist"]] == ["Suppe", "Tacos"]
    assert client.post(f"/api/plans/{plan['id']}/wishlist", json={}).status_code == 422

    wish = p["wishlist"][0]
    p = client.post(f"/api/wishlist/{wish['id']}/place", json={"date": "2026-10-06"}).json()
    assert day(p, "2026-10-06")["meal"]["title"] == "Suppe"
    assert [w["title"] for w in p["wishlist"]] == ["Tacos"]

    # Fejl ved placering: ønsket bliver på listen.
    tacos = p["wishlist"][0]
    assert client.post(f"/api/wishlist/{tacos['id']}/place", json={"date": "2027-01-01"}).status_code == 422
    assert [w["title"] for w in client.get(f"/api/plans/{plan['id']}").json()["wishlist"]] == ["Tacos"]

    p = client.delete(f"/api/wishlist/{tacos['id']}").json()
    assert p["wishlist"] == []


def test_deleted_recipe_leaves_meal(client, plan, recipes):
    p = put(client, plan, date=START, kind="opskrift", recipe_id=recipes["suppe"]["id"])
    client.delete(f"/api/recipes/{recipes['suppe']['id']}")
    meal = day(client.get(f"/api/plans/{plan['id']}").json(), START)["meal"]
    assert meal["title"] == "Slettet opskrift" and meal["lines"] == []


def test_recipe_edit_keeps_line_states(client, plan, recipes):
    p = put(client, plan, date=START, kind="opskrift", recipe_id=recipes["suppe"]["id"])
    meal = day(p, START)["meal"]
    porre = meal["lines"][1]["line_id"]
    client.put(f"/api/meals/{meal['id']}/lines/{porre}", json={"state": "hjemme"})
    rec = client.get(f"/api/recipes/{recipes['suppe']['id']}").json()
    body = {"title": "Suppe", "ingredients": [
        {k: v for k, v in l.items() if k != "ingredient"} | {"ingredient_id": l["ingredient"]["id"] if l["ingredient"] else None}
        for l in rec["ingredients"]] + [{"raw": "1 løg"}]}
    assert client.put(f"/api/recipes/{rec['id']}", json=body).status_code == 200
    lines = day(client.get(f"/api/plans/{plan['id']}").json(), START)["meal"]["lines"]
    assert [l["state"] for l in lines] == [None, "hjemme", None, None]


def test_delete_plan(client, plan):
    assert client.delete(f"/api/plans/{plan['id']}").status_code == 204
    assert client.get(f"/api/plans/{plan['id']}").status_code == 404


def test_plans_require_login(anon):
    assert anon.get("/api/plans").status_code == 401
    assert anon.post("/api/plans", json={"start_date": str(date.today())}).status_code == 401


def test_distribute_wishes_to_free_days(client, plan, recipes):
    put(client, plan, date="2026-10-04", kind="fritekst", text="Pizza")
    put(client, plan, date="2026-10-06", kind="fritekst", text="Tacos")
    for r in ("kødsovs", "lasagne", "suppe"):
        client.post(f"/api/plans/{plan['id']}/wishlist", json={"recipe_id": recipes[r]["id"]})
    p = client.post(f"/api/plans/{plan['id']}/wishlist/distribute?today=2026-10-01").json()
    assert [d["meal"]["title"] if d["meal"] else None for d in p["days"]] == [
        "Pizza", "Kødsovs", "Tacos", "Lasagne", "Suppe", None, None]
    assert p["wishlist"] == []


def test_distribute_keeps_wishes_without_room(client, recipes):
    plan = client.post("/api/plans", json={"start_date": START, "days": 1}).json()
    for r in ("kødsovs", "lasagne"):
        client.post(f"/api/plans/{plan['id']}/wishlist", json={"recipe_id": recipes[r]["id"]})
    p = client.post(f"/api/plans/{plan['id']}/wishlist/distribute?today=2026-10-01").json()
    assert p["days"][0]["meal"]["title"] == "Kødsovs"
    assert [w["title"] for w in p["wishlist"]] == ["Lasagne"]


def test_distribute_skips_days_that_have_passed(client, plan, recipes):
    for r in ("kødsovs", "lasagne"):
        client.post(f"/api/plans/{plan['id']}/wishlist", json={"recipe_id": recipes[r]["id"]})
    # Onsdag i planens uge: søn-tirs er gået.
    p = client.post(f"/api/plans/{plan['id']}/wishlist/distribute?today=2026-10-07").json()
    assert [d["meal"]["title"] if d["meal"] else None for d in p["days"]] == [
        None, None, None, "Kødsovs", "Lasagne", None, None]
