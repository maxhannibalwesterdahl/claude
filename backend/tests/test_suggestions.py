from datetime import datetime, timezone

import pytest

from madplan.models import Recipe

OLD = "2026-09-20"    # søndag, en ældre plan
START = "2026-10-04"  # søndag, "denne uge"


@pytest.fixture
def recipes(client):
    def make(title, **extra):
        r = client.post("/api/recipes", json={"title": title, "servings": 4, **extra})
        assert r.status_code == 201, r.text
        return r.json()
    return {
        "kødsovs": make("Kødsovs"),
        "lasagne": make("Lasagne", source_url="https://www.valdemarsro.dk/lasagne/"),
        "suppe": make("Suppe"),
    }


def new_plan(client, start):
    r = client.post("/api/plans", json={"start_date": start})
    assert r.status_code == 201, r.text
    return r.json()


@pytest.fixture
def plan(client):
    return new_plan(client, START)


@pytest.fixture
def old(client):
    return new_plan(client, OLD)


def put(client, plan, **slot):
    r = client.put(f"/api/plans/{plan['id']}/slots", json=slot)
    assert r.status_code == 200, r.text
    return r.json()


def get(client, **params):
    r = client.get("/api/suggestions", params=params)
    assert r.status_code == 200, r.text
    return r.json()


def rows(client, **params):
    return [(s["recipe"]["title"], s["last_planned"]) for s in get(client, **params)]


def test_requires_login(anon):
    assert anon.get("/api/suggestions").status_code == 401


def test_no_recipes_is_empty(client):
    assert get(client) == []


def test_without_plans_all_recipes_in_creation_order(client, recipes):
    assert rows(client) == [("Kødsovs", None), ("Lasagne", None), ("Suppe", None)]


def test_oldest_first_and_never_planned_last(client, recipes, old, plan):
    put(client, plan, date=START, kind="opskrift", recipe_id=recipes["kødsovs"]["id"])
    put(client, old, date=OLD, kind="opskrift", recipe_id=recipes["suppe"]["id"])
    assert rows(client) == [("Suppe", OLD), ("Kødsovs", START), ("Lasagne", None)]


def test_latest_date_wins_across_plans_and_days(client, recipes, old, plan):
    rid = recipes["suppe"]["id"]
    put(client, old, date=OLD, kind="opskrift", recipe_id=rid)
    put(client, old, date="2026-09-23", kind="opskrift", recipe_id=rid)
    assert rows(client)[0] == ("Suppe", "2026-09-23")
    put(client, plan, date="2026-10-06", kind="opskrift", recipe_id=rid)
    put(client, plan, date=START, kind="opskrift", recipe_id=rid)
    assert ("Suppe", "2026-10-06") in rows(client)


def test_child_meal_counts_as_planned(client, recipes, old):
    put(client, old, date=OLD, for_child=True, kind="opskrift", recipe_id=recipes["lasagne"]["id"])
    assert rows(client)[0] == ("Lasagne", OLD)


def test_plan_id_excludes_meals_child_meals_and_wishes(client, recipes, plan):
    pid = plan["id"]
    assert len(get(client, plan_id=pid)) == 3
    # Fritekst som ret og som ønske udelader ingenting.
    put(client, plan, date=START, kind="fritekst", text="Lasagne")
    client.post(f"/api/plans/{pid}/wishlist", json={"text": "Suppe"})
    assert len(get(client, plan_id=pid)) == 3

    put(client, plan, date="2026-10-05", kind="opskrift", recipe_id=recipes["kødsovs"]["id"])
    assert rows(client, plan_id=pid) == [("Lasagne", None), ("Suppe", None)]
    put(client, plan, date="2026-10-05", for_child=True, kind="opskrift", recipe_id=recipes["lasagne"]["id"])
    assert rows(client, plan_id=pid) == [("Suppe", None)]
    client.post(f"/api/plans/{pid}/wishlist", json={"recipe_id": recipes["suppe"]["id"]})
    assert rows(client, plan_id=pid) == []


def test_plan_id_only_excludes_that_plans_recipes(client, recipes, old, plan):
    put(client, old, date=OLD, kind="opskrift", recipe_id=recipes["suppe"]["id"])
    client.post(f"/api/plans/{old['id']}/wishlist", json={"recipe_id": recipes["lasagne"]["id"]})
    assert rows(client, plan_id=plan["id"]) == [("Suppe", OLD), ("Kødsovs", None), ("Lasagne", None)]


def test_plan_id_ignores_the_plans_own_dates(client, recipes, old, plan):
    rid = recipes["suppe"]["id"]
    put(client, old, date=OLD, kind="opskrift", recipe_id=rid)
    p = put(client, plan, date=START, kind="opskrift", recipe_id=rid)
    assert "Suppe" not in [t for t, _ in rows(client, plan_id=plan["id"])]
    # Taget af planen igen: datoen kommer fra den anden plan.
    meal = next(d["meal"] for d in p["days"] if d["date"] == START)
    client.delete(f"/api/meals/{meal['id']}")
    assert rows(client, plan_id=plan["id"])[0] == ("Suppe", OLD)


def test_without_plan_id_every_plan_counts(client, recipes, old, plan):
    rid = recipes["suppe"]["id"]
    put(client, old, date=OLD, kind="opskrift", recipe_id=rid)
    put(client, plan, date="2026-10-07", kind="opskrift", recipe_id=rid)
    assert rows(client) == [("Suppe", "2026-10-07"), ("Kødsovs", None), ("Lasagne", None)]
    # Set fra den gamle plan er opskriften sidst lavet i den nye uge, men står selv på planen.
    assert rows(client, plan_id=old["id"]) == [("Kødsovs", None), ("Lasagne", None)]


def test_limit_applies_after_ordering(client, recipes, old):
    put(client, old, date=OLD, kind="opskrift", recipe_id=recipes["suppe"]["id"])
    assert rows(client, limit=1) == [("Suppe", OLD)]
    assert len(get(client, limit=2)) == 2
    assert len(get(client, limit=500)) == 3


@pytest.mark.parametrize("limit", [0, -1, 501, "mange"])
def test_limit_out_of_range_is_422(client, limit):
    assert client.get("/api/suggestions", params={"limit": limit}).status_code == 422


def test_unknown_plan_is_404(client, recipes):
    r = client.get("/api/suggestions?plan_id=999")
    assert r.status_code == 404 and r.json()["detail"] == "Planen findes ikke"
    assert client.get("/api/suggestions?plan_id=abc").status_code == 422


def test_deleted_recipe_disappears(client, recipes, old):
    put(client, old, date=OLD, kind="opskrift", recipe_id=recipes["suppe"]["id"])
    assert client.delete(f"/api/recipes/{recipes['suppe']['id']}").status_code == 204
    assert rows(client) == [("Kødsovs", None), ("Lasagne", None)]
    assert rows(client, plan_id=old["id"]) == [("Kødsovs", None), ("Lasagne", None)]


def test_leftovers_do_not_count_as_planned(client, recipes, old):
    p = put(client, old, date=OLD, kind="opskrift", recipe_id=recipes["suppe"]["id"])
    src = next(d["meal"] for d in p["days"] if d["date"] == OLD)
    put(client, old, date="2026-09-22", kind="rester", leftover_from_id=src["id"])
    assert rows(client)[0] == ("Suppe", OLD)


def test_ties_are_broken_by_title(client, app, recipes, old):
    # Samme dato: husstandens og barnets ret samme dag.
    put(client, old, date=OLD, kind="opskrift", recipe_id=recipes["suppe"]["id"])
    put(client, old, date=OLD, for_child=True, kind="opskrift", recipe_id=recipes["kødsovs"]["id"])
    assert rows(client) == [("Kødsovs", OLD), ("Suppe", OLD), ("Lasagne", None)]

    # Aldrig planlagt og oprettet i samme øjeblik: titel uden hensyn til store bogstaver, så id.
    extra = [client.post("/api/recipes", json={"title": t}).json()["id"] for t in ("b-ret", "A-ret", "a-ret")]
    with app.state.db.sessionmaker() as s:
        for r in s.query(Recipe).filter(Recipe.id.in_([*extra, recipes["lasagne"]["id"]])):
            r.created_at = datetime(2020, 1, 1, tzinfo=timezone.utc)
        s.commit()
    assert [s["recipe"]["id"] for s in get(client)][2:] == [extra[1], extra[2], extra[0], recipes["lasagne"]["id"]]


def test_response_shape(client, recipes):
    by_title = {s["recipe"]["title"]: s for s in get(client)}
    s = by_title["Lasagne"]
    assert set(s) == {"recipe", "source_host", "last_planned"}
    assert s["recipe"] == {"id": recipes["lasagne"]["id"], "title": "Lasagne", "servings": 4, "image_url": None}
    assert s["source_host"] == "valdemarsro.dk"
    assert by_title["Suppe"]["source_host"] is None and by_title["Suppe"]["last_planned"] is None
