"""QA: indkøbsliste, ugeplan og datoer – kanttilfælde og samtidighed."""

import threading
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from conftest import PASSWORD
from madplan.config import TZ
from madplan.models import MealReminder, PlanMeal
from madplan.reminders import slot_due


def recipe(client, title, lines):
    r = client.post("/api/recipes", json={"title": title, "ingredients": [{"raw": l} for l in lines]})
    assert r.status_code == 201, r.text
    return r.json()


def put(client, pid, d, rec, mult=1.0, child=False):
    r = client.put(f"/api/plans/{pid}/slots", json={"date": d, "kind": "opskrift", "recipe_id": rec["id"],
                                                    "multiplier": mult, "for_child": child})
    assert r.status_code == 200, r.text
    return r.json()


def by_name(data):
    return {i["name"]: i for i in data["items"]}


def amounts(item):
    return [(a["quantity"], a["unit"]) for a in item["amounts"]]


# --- Datoer: årsskifte, uge 53, sommertid ---------------------------------------------

def test_plan_across_new_year_and_week_53(client):
    """2026 har uge 53 (28/12-3/1). Planen skal bare være 7 kalenderdage."""
    p = client.post("/api/plans", json={"start_date": "2026-12-28"}).json()
    assert [d["date"] for d in p["days"]] == [
        "2026-12-28", "2026-12-29", "2026-12-30", "2026-12-31", "2027-01-01", "2027-01-02", "2027-01-03"]
    assert p["end_date"] == "2027-01-03"
    # Den næste plan må begynde dagen efter, ikke dagen før.
    assert client.post("/api/plans", json={"start_date": "2027-01-03"}).status_code == 409
    assert client.post("/api/plans", json={"start_date": "2027-01-04"}).status_code == 201


@pytest.mark.parametrize("today, expect_start", [
    ("2026-12-31", "2026-12-28"), ("2027-01-01", "2026-12-28"), ("2027-01-03", "2026-12-28"),
    ("2027-01-04", "2027-01-04"), ("2026-12-27", "2026-12-28"),
])
def test_current_plan_at_year_boundary(client, today, expect_start):
    client.post("/api/plans", json={"start_date": "2026-12-28"})
    client.post("/api/plans", json={"start_date": "2027-01-04"})
    got = client.get(f"/api/plans/current?today={today}").json()
    assert got["start_date"] == expect_start


def test_shopping_list_spans_year_boundary(client):
    p = client.post("/api/plans", json={"start_date": "2026-12-28"}).json()
    sovs = recipe(client, "Sovs", ["2 løg"])
    put(client, p["id"], "2026-12-31", sovs)
    put(client, p["id"], "2027-01-02", sovs, 2.0)
    data = client.get(f"/api/shopping?plan_id={p['id']}&today=2027-01-01").json()
    assert amounts(by_name(data)["løg"]) == [(6.0, None)]
    assert by_name(data)["løg"]["days"] == ["2026-12-31", "2027-01-02"]


def test_leap_day_plan(client):
    p = client.post("/api/plans", json={"start_date": "2028-02-26"}).json()
    assert "2028-02-29" in [d["date"] for d in p["days"]]


@pytest.mark.parametrize("start", ["2026-10-25", "2027-03-28"])
def test_plan_over_daylight_saving_change_has_seven_distinct_days(client, start):
    """Sommertid skifter 25/10-2026 og 28/3-2027: ingen dag må forsvinde eller fordobles."""
    p = client.post("/api/plans", json={"start_date": start}).json()
    dates = [d["date"] for d in p["days"]]
    assert len(dates) == len(set(dates)) == 7


def test_reminder_slot_on_dst_night():
    """Natten til 25/10-2026 er kl. 02:30 lokal tid to gange. Påmindelsen kl. 19 må ikke påvirkes."""
    r = MealReminder(text="x", again_on=True, meal=PlanMeal(date=datetime(2026, 10, 25).date()))
    assert not slot_due(r, datetime(2026, 10, 24, 18, 59, tzinfo=TZ))
    assert slot_due(r, datetime(2026, 10, 24, 19, 0, tzinfo=TZ))
    assert slot_due(r, datetime(2026, 10, 25, 7, 0, tzinfo=TZ))
    assert not slot_due(r, datetime(2026, 10, 26, 7, 0, tzinfo=TZ))


def test_plan_with_extreme_date_is_422_not_500(app, anon):
    c = TestClient(app, raise_server_exceptions=False)
    c.post("/api/login", json={"username": "max", "password": PASSWORD})
    assert c.post("/api/plans", json={"start_date": "9999-12-30", "days": 7}).status_code == 422


# --- Mængder og ugens samlede liste -----------------------------------------------------

def test_child_meal_and_half_portion_count_on_the_list(client):
    p = client.post("/api/plans", json={"start_date": "2026-10-04"}).json()
    sovs = recipe(client, "Sovs", ["1 dåse tomater", "400 g hakket oksekød"])
    put(client, p["id"], "2026-10-04", sovs)
    put(client, p["id"], "2026-10-04", sovs, 0.5, child=True)
    it = by_name(client.get("/api/shopping?today=2026-10-01").json())
    # 1 dåse + ½ dåse (rundet op til 1 dåse for barnet) = 2 dåser; kød 400 + 200 g
    assert amounts(it["tomat"]) == [(2.0, "dåse")]
    assert amounts(it["hakket oksekød"]) == [(600.0, "g")]


def test_deleted_recipe_disappears_from_list_without_error(client):
    p = client.post("/api/plans", json={"start_date": "2026-10-04"}).json()
    r = recipe(client, "Sovs", ["2 løg"])
    put(client, p["id"], "2026-10-04", r)
    client.delete(f"/api/recipes/{r['id']}")
    data = client.get("/api/shopping?today=2026-10-01")
    assert data.status_code == 200 and data.json()["items"] == []
    day = client.get(f"/api/plans/{p['id']}").json()["days"][0]["meal"]
    assert day["title"] == "Slettet opskrift"


def test_recipe_edit_changes_list_but_keeps_checked_state(client):
    p = client.post("/api/plans", json={"start_date": "2026-10-04"}).json()
    r = recipe(client, "Sovs", ["2 løg", "1 dåse tomater"])
    put(client, p["id"], "2026-10-04", r)
    key = by_name(client.get("/api/shopping?today=2026-10-01").json())["løg"]["key"]
    client.post("/api/shopping/sync?today=2026-10-01", json={"plan_id": p["id"], "changes": [{"key": key, "checked": True, "ts": 5}]})
    body = {"title": "Sovs", "ingredients": [
        {"id": l["id"], "raw": "3 løg" if l["item"] == "løg" else l["raw"]} for l in r["ingredients"]]}
    assert client.put(f"/api/recipes/{r['id']}", json=body).status_code == 200
    it = by_name(client.get("/api/shopping?today=2026-10-01").json())
    assert amounts(it["løg"]) == [(3.0, None)] and it["løg"]["checked"]


def test_shopping_checks_are_kept_per_plan(client):
    a = client.post("/api/plans", json={"start_date": "2026-10-04"}).json()
    b = client.post("/api/plans", json={"start_date": "2026-10-11"}).json()
    r = recipe(client, "Sovs", ["2 løg"])
    put(client, a["id"], "2026-10-04", r)
    put(client, b["id"], "2026-10-11", r)
    key = by_name(client.get(f"/api/shopping?plan_id={a['id']}").json())["løg"]["key"]
    client.post("/api/shopping/sync", json={"plan_id": a["id"], "view_plan_id": a["id"],
                                            "changes": [{"key": key, "checked": True, "ts": 9}]})
    assert by_name(client.get(f"/api/shopping?plan_id={a['id']}").json())["løg"]["checked"]
    assert not by_name(client.get(f"/api/shopping?plan_id={b['id']}").json())["løg"]["checked"]


def test_plan_delete_removes_checks_and_meals_but_not_recipes(client):
    p = client.post("/api/plans", json={"start_date": "2026-10-04"}).json()
    r = recipe(client, "Sovs", ["2 løg"])
    put(client, p["id"], "2026-10-04", r)
    key = by_name(client.get(f"/api/shopping?plan_id={p['id']}").json())["løg"]["key"]
    client.post("/api/shopping/sync", json={"plan_id": p["id"], "changes": [{"key": key, "checked": True, "ts": 9}]})
    assert client.delete(f"/api/plans/{p['id']}").status_code == 204
    assert client.get(f"/api/recipes/{r['id']}").status_code == 200
    assert client.get(f"/api/plans/{p['id']}").status_code == 404


# --- Egne varer, tekst og tal -----------------------------------------------------------

@pytest.mark.parametrize("text", ["æøå ÆØÅ 🍎🍞", "x" * 200, "2 pk bleer", "99999999999 mælk", "<b>fed</b> & 'citat'"])
def test_extra_accepts_odd_text_and_returns_it_unchanged_in_content(client, text):
    r = client.post("/api/shopping/extras", json={"text": text})
    assert r.status_code == 201
    assert any(i["name"] == " ".join(text.split()) for i in r.json()["items"])


@pytest.mark.parametrize("text", ["", "   ", "\n\t"])
def test_extra_rejects_blank(client, text):
    assert client.post("/api/shopping/extras", json={"text": text}).status_code == 422


def test_extra_longer_than_200_is_rejected(client):
    assert client.post("/api/shopping/extras", json={"text": "x" * 201}).status_code == 422


def test_extra_unknown_ingredient_is_404(client):
    assert client.post("/api/shopping/extras", json={"text": "x", "ingredient_id": 999999}).status_code == 404


def test_out_of_stock_twice_gives_one_row(client):
    p = client.post("/api/plans", json={"start_date": "2026-10-04"}).json()
    r = recipe(client, "Sovs", ["1 tsk salt"])
    put(client, p["id"], "2026-10-04", r)
    pantry = client.get("/api/shopping?today=2026-10-01").json()["pantry"][0]
    for _ in range(3):
        d = client.post("/api/shopping/extras?today=2026-10-01",
                        json={"ingredient_id": pantry["ingredient_id"], "source": "løbet tør"}).json()
    assert sum(1 for i in d["items"] if i["source"] == "løbet tør") == 1


def test_double_submit_of_same_extra_gives_one_row(client):
    client.post("/api/shopping/extras", json={"text": "banan"})
    d = client.post("/api/shopping/extras", json={"text": "banan"}).json()
    assert sum(1 for i in d["items"] if i["name"] == "banan") == 1


def test_department_order_must_be_complete_and_applies_to_list(client):
    cur = [d["code"] for d in client.get("/api/settings/departments").json()]
    assert client.put("/api/settings/departments", json={"order": cur[:-1]}).status_code == 422
    assert client.put("/api/settings/departments", json={"order": cur[:-1] + [cur[0]]}).status_code == 422
    assert client.put("/api/settings/departments", json={"order": cur[::-1]}).status_code == 200
    p = client.post("/api/plans", json={"start_date": "2026-10-04"}).json()
    r = recipe(client, "Sovs", ["2 løg", "400 g hakket oksekød", "3 dl mælk"])
    put(client, p["id"], "2026-10-04", r)
    depts = [i["department"] for i in client.get("/api/shopping?today=2026-10-01").json()["items"]]
    rank = {c: i for i, c in enumerate(cur[::-1])}
    assert depts == sorted(depts, key=lambda d: rank[d])


# --- Sync fra flere enheder -------------------------------------------------------------

def test_sync_ignores_garbage_changes_and_clamps_far_future(client):
    p = client.post("/api/plans", json={"start_date": "2026-10-04"}).json()
    r = recipe(client, "Sovs", ["2 løg"])
    put(client, p["id"], "2026-10-04", r)
    key = by_name(client.get("/api/shopping?today=2026-10-01").json())["løg"]["key"]
    far = 10**13
    res = client.post("/api/shopping/sync?today=2026-10-01", json={"plan_id": p["id"], "changes": [
        {"junk": 1}, {"key": "zz:1", "checked": True, "ts": 1}, {"key": "e:abc", "checked": True, "ts": 1},
        {"key": "e:99999", "checked": True, "ts": 1}, {"key": key, "checked": True, "ts": far}]})
    assert res.status_code == 200
    # Uret langt fremme låser ikke rækken: en rigtig ændring lidt senere vinder.
    import time
    later = int(time.time() * 1000) + 120_000
    res = client.post("/api/shopping/sync?today=2026-10-01", json={"plan_id": p["id"], "changes": [
        {"key": key, "checked": False, "ts": later}]})
    assert not by_name(res.json())["løg"]["checked"]


def test_sync_equal_timestamp_keeps_first_writer(client):
    p = client.post("/api/plans", json={"start_date": "2026-10-04"}).json()
    r = recipe(client, "Sovs", ["2 løg"])
    put(client, p["id"], "2026-10-04", r)
    key = by_name(client.get("/api/shopping?today=2026-10-01").json())["løg"]["key"]
    client.post("/api/shopping/sync?today=2026-10-01", json={"plan_id": p["id"], "changes": [{"key": key, "checked": True, "ts": 100}]})
    res = client.post("/api/shopping/sync?today=2026-10-01", json={"plan_id": p["id"], "changes": [{"key": key, "checked": False, "ts": 100}]})
    assert by_name(res.json())["løg"]["checked"]


def test_sync_for_deleted_plan_is_ignored_not_500(client):
    res = client.post("/api/shopping/sync", json={"plan_id": 4242, "changes": [{"key": "i:1", "checked": True, "ts": 1, "plan_id": 4242}]})
    assert res.status_code == 200


def test_two_devices_check_same_new_item_at_once(app, client):
    p = client.post("/api/plans", json={"start_date": "2026-10-04"}).json()
    statuses = []

    def go(c, key, i, barrier):
        barrier.wait()
        statuses.append(c.post("/api/shopping/sync?today=2026-10-01", json={"plan_id": p["id"], "changes": [
            {"key": key, "checked": True, "ts": 1000 + i, "plan_id": p["id"]}]}).status_code)

    clients = []
    for _ in range(6):
        c = TestClient(app, raise_server_exceptions=False)
        c.cookies.update(client.cookies)
        clients.append(c)
    for rnd in range(15):  # nye nøgler hver runde, så rækken ikke findes i forvejen
        barrier = threading.Barrier(6)
        ts = [threading.Thread(target=go, args=(clients[i], f"t:race{rnd}", i, barrier)) for i in range(6)]
        [t.start() for t in ts]
        [t.join() for t in ts]
    assert statuses == [200] * len(statuses)


def test_concurrent_edits_to_different_meals_are_all_kept(app, client):
    """To enheder planlægger hver sin dag samtidigt: begge retter skal blive."""
    p = client.post("/api/plans", json={"start_date": "2026-10-04"}).json()
    r = recipe(client, "Sovs", ["2 løg"])
    barrier, codes = threading.Barrier(2), []

    def go(day):
        c = TestClient(app)
        c.cookies.update(client.cookies)
        barrier.wait()
        codes.append(c.put(f"/api/plans/{p['id']}/slots", json={"date": day, "kind": "opskrift", "recipe_id": r["id"]}).status_code)

    ts = [threading.Thread(target=go, args=(d,)) for d in ("2026-10-04", "2026-10-05")]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert codes == [200, 200]
    days = client.get(f"/api/plans/{p['id']}").json()["days"]
    assert days[0]["meal"] and days[1]["meal"]


def test_double_submit_of_new_plan_gives_one_plan_and_409(client):
    assert client.post("/api/plans", json={"start_date": "2026-10-04"}).status_code == 201
    assert client.post("/api/plans", json={"start_date": "2026-10-04"}).status_code == 409
    assert len(client.get("/api/plans").json()) == 1


def test_double_distribute_does_not_duplicate(client):
    p = client.post("/api/plans", json={"start_date": "2026-10-04"}).json()
    for i in range(3):
        client.post(f"/api/plans/{p['id']}/wishlist", json={"text": f"ønske {i}"})
    for _ in range(2):
        out = client.post(f"/api/plans/{p['id']}/wishlist/distribute?today=2026-10-01").json()
    assert [d["meal"]["title"] for d in out["days"][:3]] == ["ønske 0", "ønske 1", "ønske 2"]
    assert out["wishlist"] == []


def test_home_with_unknown_plan_is_404(client):
    assert client.post("/api/shopping/home", json={"plan_id": 999, "key": "i:1", "home": True}).status_code == 404
