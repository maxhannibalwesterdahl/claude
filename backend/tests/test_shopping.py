import pytest
from conftest import ingredient_id

from madplan.shopping import Amount, combine

START = "2026-10-04"


# --- Sammenlægning -----------------------------------------------------------------

@pytest.mark.parametrize("parts, gpp, gpd, expected", [
    # Samme enhed
    ([(1, "dåse"), (1, "dåse")], None, None, [Amount(2, "dåse")]),
    ([(2, "spsk"), (1, "spsk")], None, None, [Amount(3, "spsk")]),
    ([(2, None), (1.5, None)], None, None, [Amount(4, None)]),  # stk rundes op
    ([(600, "g"), (500, "g")], None, None, [Amount(1.1, "kg")]),
    ([(0.5, "kg")], None, None, [Amount(500, "g")]),
    ([(3, "dl"), (8, "dl")], None, None, [Amount(1.1, "l")]),
    ([(0.1, "dl"), (0.2, "dl")], None, None, [Amount(30, "ml")]),
    ([(1, "stk"), (2, None)], None, None, [Amount(3, None)]),
    # Spec-eksemplet: 2 løg + 150 g løg = 3 løg
    ([(2, None), (150, "g")], 150, None, [Amount(3, None)]),
    ([(2, None), (100, "g")], 150, None, [Amount(3, None)]),  # 2,67 -> 3
    # Vægt og rumfang lægges sammen via g/dl
    ([(500, "g"), (2, "dl")], None, 60, [Amount(620, "g")]),
    # dl + spsk uden g/dl: begge er rumfang
    ([(1, "dl"), (2, "spsk")], None, None, [Amount(1.3, "dl")]),
    # Kan ikke omregnes: vises hver for sig
    ([(2, None), (150, "g")], None, None, [Amount(2, None), Amount(150, "g")]),
    ([(1, "bundt"), (2, "spsk")], None, None, [Amount(30, "ml"), Amount(1, "bundt")]),
    ([], None, None, []),
    # Hele pakninger (SPEC §2.4): ½ dåse købes som 1 dåse.
    ([(0.5, "dåse")], None, None, [Amount(1, "dåse")]),
    ([(0.5, "dåse"), (1, "dåse")], None, None, [Amount(2, "dåse")]),
    ([(1.5, "fed")], None, None, [Amount(2, "fed")]),
    ([(0.5, "dåse"), (100, "g")], None, None, [Amount(100, "g"), Amount(1, "dåse")]),
])
def test_combine(parts, gpp, gpd, expected):
    assert combine(parts, gpp, gpd) == expected


# --- API ------------------------------------------------------------------------

@pytest.fixture
def week(client):
    def recipe(title, lines):
        return client.post("/api/recipes", json={"title": title, "ingredients": [{"raw": l} for l in lines]}).json()

    sovs = recipe("Kødsovs", ["500 g hakket oksekød", "2 løg", "1 dåse hakkede tomater", "salt og peber", "1 bundt persille"])
    suppe = recipe("Suppe", ["150 g løg", "3 gulerødder", "2 dl piskefløde", "1 stk dragefrugt"])
    las = recipe("Lasagne", ["500 g hakket oksekød", "1 dåse hakkede tomater", "3 dl mælk"])
    plan = client.post("/api/plans", json={"start_date": START}).json()

    def put(d, r, mult=1):
        return client.put(f"/api/plans/{plan['id']}/slots",
                          json={"date": d, "kind": "opskrift", "recipe_id": r["id"], "multiplier": mult}).json()

    put("2026-10-04", sovs)
    put("2026-10-05", suppe, 2)
    p = put("2026-10-07", las)
    # Lasagnen bruger rest af kødsovsen: kødet er dækket.
    las_meal = p["days"][3]["meal"]
    client.patch(f"/api/meals/{las_meal['id']}", json={"leftover_from_id": p["days"][0]["meal"]["id"]})
    client.put(f"/api/meals/{las_meal['id']}/lines/{las_meal['lines'][0]['line_id']}", json={"state": "rest"})
    return plan


def items(data):
    return {i["name"]: i for i in data["items"]}


def fmt(item):
    return [(a["quantity"], a["unit"]) for a in item["amounts"]]


def test_list_combines_the_week(client, week):
    data = client.get("/api/shopping?today=2026-10-01").json()
    assert data["plan"]["id"] == week["id"]
    it = items(data)
    # 2 løg (søn) + 150 g løg ×2 (man) = 2 + 2 = 4 stk
    assert fmt(it["løg"]) == [(4, None)] and it["løg"]["days"] == ["2026-10-04", "2026-10-05"]
    # Kød kun fra kødsovsen; lasagnens kød er dækket af rest.
    assert fmt(it["hakket oksekød"]) == [(500, "g")]
    assert fmt(it["hakkede tomater"]) == [(2, "dåse")]
    assert fmt(it["piskefløde"]) == [(4, "dl")]
    assert fmt(it["gulerod"]) == [(6, None)]
    assert fmt(it["persille"]) == [(1, "bundt")]
    # Uden kendt vare
    assert it["dragefrugt"]["unknown"] and it["dragefrugt"]["department"] == "andet"
    # Basisvarer er ikke på listen, men i sektionen for basisvarer.
    assert "salt og peber" not in it
    assert [p["name"] for p in data["pantry"]] == ["salt og peber"]
    # Sorteret efter afdeling: frugt & grønt før kød før mejeri.
    depts = [i["department"] for i in data["items"]]
    assert depts.index("fg") < depts.index("kod") < depts.index("mej") < depts.index("andet")
    assert [s["meal"] for s in it["løg"]["sources"]] == ["Kødsovs", "Suppe (×2)"]


def test_sync_last_write_wins(client, week):
    r = client.post("/api/shopping/sync?today=2026-10-01", json={"plan_id": week["id"], "changes": [
        {"key": items(client.get("/api/shopping?today=2026-10-01").json())["løg"]["key"], "checked": True, "ts": 2000}]})
    key = items(r.json())["løg"]["key"]
    assert items(r.json())["løg"]["checked"]
    # En ældre ændring fra den anden telefon taber.
    r = client.post("/api/shopping/sync?today=2026-10-01", json={"plan_id": week["id"], "changes": [{"key": key, "checked": False, "ts": 1000}]})
    assert items(r.json())["løg"]["checked"]
    r = client.post("/api/shopping/sync?today=2026-10-01", json={"plan_id": week["id"], "changes": [{"key": key, "checked": False, "ts": 3000}]})
    assert not items(r.json())["løg"]["checked"]


def test_home_removes_item_and_can_be_undone(client, week):
    key = items(client.get("/api/shopping?today=2026-10-01").json())["hakkede tomater"]["key"]
    data = client.post("/api/shopping/home", json={"plan_id": week["id"], "key": key, "home": True}).json()
    assert "hakkede tomater" not in items(data)
    assert data["home"] == [{"key": key, "name": "hakkede tomater"}]
    # Også markeret i madplanen.
    plan = client.get(f"/api/plans/{week['id']}").json()
    assert [l["state"] for l in plan["days"][0]["meal"]["lines"] if l["item"] == "hakkede tomater"] == ["hjemme"]
    data = client.post("/api/shopping/home", json={"plan_id": week["id"], "key": key, "home": False}).json()
    assert fmt(items(data)["hakkede tomater"]) == [(2, "dåse")]


def test_extras(client, week):
    data = client.post("/api/shopping/extras?today=2026-10-01", json={"text": "bleer"}).json()
    data = client.post("/api/shopping/extras?today=2026-10-01", json={"text": "Kaffe"}).json()
    it = items(data)
    assert it["bleer"]["kind"] == "extra" and it["bleer"]["department"] == "baby"
    assert client.post("/api/shopping/extras?today=2026-10-01", json={"text": "  "}).status_code == 422

    # Kendt vare kommer i sin afdeling.
    data = client.post("/api/shopping/extras?today=2026-10-01", json={"text": "2 liter mælk"}).json()
    assert items(data)["2 liter mælk"]["department"] == "mej"

    key = it["bleer"]["key"]
    data = client.post("/api/shopping/sync?today=2026-10-01", json={"changes": [{"key": key, "checked": True, "ts": 10**13}]}).json()
    assert items(data)["bleer"]["checked"]
    data = client.delete(f"/api/shopping/extras/{key[2:]}?today=2026-10-01").json()
    assert "bleer" not in items(data)


def test_bought_extras_disappear_later(client, app, week):
    data = client.post("/api/shopping/extras?today=2026-10-01", json={"text": "bleer"}).json()
    key = items(data)["bleer"]["key"]
    # Krydset af for længe siden (ts = 1): vises ikke længere.
    data = client.post("/api/shopping/sync?today=2026-10-01", json={"changes": [{"key": key, "checked": True, "ts": 1}]}).json()
    assert "bleer" not in items(data)


def test_unbought_extras_follow_to_next_plan(client, week):
    client.post("/api/shopping/extras?today=2026-10-01", json={"text": "bleer"})
    nxt = client.post("/api/plans", json={"start_date": "2026-10-11"}).json()
    data = client.get(f"/api/shopping?plan_id={nxt['id']}&today=2026-10-01").json()
    assert "bleer" in items(data)


def test_out_of_stock_pantry_item(client, week):
    data = client.get("/api/shopping?today=2026-10-01").json()
    salt = data["pantry"][0]
    data = client.post("/api/shopping/extras?today=2026-10-01", json={"ingredient_id": salt["ingredient_id"], "source": "løbet tør"}).json()
    assert data["pantry"][0]["requested"]
    it = items(data)["salt og peber"]
    assert it["source"] == "løbet tør" and it["department"] == "kry"
    # To tryk giver ikke to rækker.
    data = client.post("/api/shopping/extras?today=2026-10-01", json={"ingredient_id": salt["ingredient_id"], "source": "løbet tør"}).json()
    assert [i["name"] for i in data["items"]].count("salt og peber") == 1


def test_choose_plan(client):
    a = client.post("/api/plans", json={"start_date": "2026-10-04"}).json()
    b = client.post("/api/plans", json={"start_date": "2026-10-11"}).json()
    # Den igangværende uge (som Planlæg), også når næste uges plan findes.
    assert client.get("/api/shopping?today=2026-10-04").json()["plan"]["id"] == a["id"]
    assert client.get("/api/shopping?today=2026-10-10").json()["plan"]["id"] == a["id"]
    assert client.get("/api/shopping?today=2026-10-11").json()["plan"]["id"] == b["id"]
    # Før første plan: den næste. Efter sidste: den seneste.
    assert client.get("/api/shopping?today=2026-10-01").json()["plan"]["id"] == a["id"]
    assert client.get("/api/shopping?today=2026-10-30").json()["plan"]["id"] == b["id"]
    # Samme uge som Planlæg åbner på.
    for d in ("2026-10-01", "2026-10-07", "2026-10-11", "2026-10-30"):
        assert client.get(f"/api/shopping?today={d}").json()["plan"]["id"] == client.get(f"/api/plans/current?today={d}").json()["id"]


def test_no_plan_still_shows_extras(client):
    data = client.post("/api/shopping/extras?today=2026-10-01", json={"text": "bleer"}).json()
    assert data["plan"] is None and [i["name"] for i in data["items"]] == ["bleer"]


def test_department_order(client, week):
    order = [d["code"] for d in client.get("/api/settings/departments").json()]
    assert order[0] == "fg"
    new = ["mej"] + [c for c in order if c != "mej"]
    assert client.put("/api/settings/departments", json={"order": new}).status_code == 200
    data = client.get("/api/shopping?today=2026-10-01").json()
    assert data["items"][0]["department"] == "mej"
    assert client.put("/api/settings/departments", json={"order": ["mej"]}).status_code == 422


def test_deleted_plan_clears_list_but_keeps_extras(client, week):
    client.post("/api/shopping/extras?today=2026-10-01", json={"text": "bleer"})
    key = items(client.get("/api/shopping?today=2026-10-01").json())["løg"]["key"]
    client.delete(f"/api/plans/{week['id']}")
    # Telefonen husker den slettede plan og har en ventende afkrydsning.
    r = client.post("/api/shopping/sync?today=2026-10-01", json={"plan_id": week["id"], "changes": [{"key": key, "checked": True, "ts": 5}]})
    assert r.status_code == 200
    data = r.json()
    assert data["plan"] is None and [i["name"] for i in data["items"]] == ["bleer"]
    assert data["pantry"] == [] and data["home"] == []


def test_list_follows_to_next_plan(client, app, week):
    # Telefonen viser stadig en ældre plan (fx sidste uge) med en ventende afkrydsning.
    old = client.post("/api/plans", json={"start_date": "2026-09-01"}).json()
    r = client.post("/api/shopping/sync?today=2026-10-01", json={"plan_id": old["id"], "changes": [{"key": "i:1", "checked": True, "ts": 5}]})
    # Svaret er listen til næste indkøb ...
    assert r.json()["plan"]["id"] == week["id"]
    # ... og afkrydsningen er gemt på den plan, den blev lavet på.
    from sqlalchemy import select

    from madplan.models import ShoppingCheck
    with app.state.db.sessionmaker() as s:
        assert [(c.plan_id, c.key) for c in s.scalars(select(ShoppingCheck))] == [(old["id"], "i:1")]


def test_view_chosen_week(client, app, week):
    # Listen viser den igangværende uge, også når næste uges plan findes.
    nxt = client.post("/api/plans", json={"start_date": "2026-10-11"}).json()
    assert client.post("/api/shopping/sync?today=2026-10-07", json={"changes": []}).json()["plan"]["id"] == week["id"]
    key = items(client.get("/api/shopping?today=2026-10-07").json())["løg"]["key"]
    # Næste uge kan vælges, også ved senere synkroniseringer.
    r = client.post("/api/shopping/sync?today=2026-10-07", json={"view_plan_id": nxt["id"], "changes": []})
    assert r.json()["plan"]["id"] == nxt["id"] and r.json()["items"] == []
    # En afkrydsning gemmes på planen, den blev lavet på, selv om telefonen
    # nu viser en anden uge.
    r = client.post("/api/shopping/sync?today=2026-10-07", json={
        "plan_id": nxt["id"], "view_plan_id": week["id"],
        "changes": [{"key": key, "checked": True, "ts": 5, "plan_id": week["id"]}]})
    assert r.json()["plan"]["id"] == week["id"] and items(r.json())["løg"]["checked"]
    # Slettes den valgte plan, vises den igangværende uge igen.
    client.delete(f"/api/plans/{nxt['id']}")
    r = client.post("/api/shopping/sync?today=2026-10-07", json={"view_plan_id": nxt["id"], "changes": []})
    assert r.json()["plan"]["id"] == week["id"]


def test_one_invalid_change_does_not_block_the_rest(client, week):
    key = items(client.get("/api/shopping?today=2026-10-01").json())["løg"]["key"]
    r = client.post("/api/shopping/sync?today=2026-10-01", json={"plan_id": week["id"], "changes": [
        {"key": "t:" + "x" * 400, "checked": True, "ts": 1000},   # for lang
        {"key": key},                                              # mangler felter
        {"key": key, "checked": True, "ts": 2000},
    ]})
    assert r.status_code == 200 and items(r.json())["løg"]["checked"]


def test_clock_far_ahead_cannot_lock_a_row(client, week):
    import time
    key = items(client.get("/api/shopping?today=2026-10-01").json())["løg"]["key"]
    far = int(time.time() * 1000) + 10 * 365 * 86400 * 1000  # ur 10 år foran
    client.post("/api/shopping/sync?today=2026-10-01", json={"plan_id": week["id"], "changes": [{"key": key, "checked": True, "ts": far}]})
    now = int(time.time() * 1000) + 120_000
    r = client.post("/api/shopping/sync?today=2026-10-01", json={"plan_id": week["id"], "changes": [{"key": key, "checked": False, "ts": now}]})
    assert not items(r.json())["løg"]["checked"]
    # Enorme tal giver ikke 500.
    r = client.post("/api/shopping/sync?today=2026-10-01", json={"changes": [{"key": key, "checked": True, "ts": 2**70}]})
    assert r.status_code == 200


def test_extra_with_chosen_ingredient_is_sorted_and_learned(client, week):
    bleer = ingredient_id(client, "bleer")
    # Appen kender ikke "pampers str 4"; brugeren vælger bleer i vare-vælgeren.
    data = client.post("/api/shopping/extras?today=2026-10-01", json={"text": "2 pk Pampers str 4", "ingredient_id": bleer}).json()
    it = items(data)["2 pk Pampers str 4"]
    assert it["department"] == "baby" and it["ingredient_name"] == "bleer" and not it["unknown"]
    # Næste gang genkendes "pampers" af sig selv.
    data = client.post("/api/shopping/extras?today=2026-10-01", json={"text": "pampers"}).json()
    assert items(data)["pampers"]["ingredient_name"] == "bleer"


def test_change_ingredient_on_extra(client, week):
    data = client.post("/api/shopping/extras?today=2026-10-01", json={"text": "gummiand"}).json()
    it = items(data)["gummiand"]
    assert it["unknown"] and it["department"] == "andet"
    toy = client.post("/api/ingredients", json={"name": "legetøj", "department": "baby"}).json()
    data = client.patch(f"/api/shopping/extras/{it['key'][2:]}?today=2026-10-01", json={"ingredient_id": toy["id"]}).json()
    it = items(data)["gummiand"]
    assert it["department"] == "baby" and it["ingredient_name"] == "legetøj"
    data = client.patch(f"/api/shopping/extras/{it['key'][2:]}?today=2026-10-01", json={"ingredient_id": None}).json()
    assert items(data)["gummiand"]["department"] == "andet"
