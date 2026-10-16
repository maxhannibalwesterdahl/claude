"""QA: tomme felter, lange tekster, specialtegn, tal og billeder."""

import pytest
from fastapi.testclient import TestClient

from conftest import PASSWORD, make_system_admin

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64
JPG = b"\xff\xd8\xff\xe0" + b"0" * 64


def safe(app, anon_client):
    """Klient, der returnerer 500 i stedet for at kaste, så fejlen kan måles."""
    c = TestClient(app, raise_server_exceptions=False)
    c.cookies.update(anon_client.cookies)
    return c


# --- Opskrifter ---------------------------------------------------------------------------

@pytest.mark.parametrize("title", ["Æblegrød med Ø og 🍎", "ø" * 200, "<script>alert(1)</script>", "a'b\"c;--", "日本語 ١٢٣"])
def test_recipe_title_roundtrips_special_text(client, title):
    r = client.post("/api/recipes", json={"title": title})
    assert r.status_code == 201
    assert client.get(f"/api/recipes/{r.json()['id']}").json()["title"] == title


def test_recipe_title_too_long_or_empty(client):
    assert client.post("/api/recipes", json={"title": ""}).status_code == 422
    assert client.post("/api/recipes", json={"title": "x" * 201}).status_code == 422


def test_recipe_title_of_only_spaces_is_rejected(client):
    assert client.post("/api/recipes", json={"title": "   "}).status_code == 422


@pytest.mark.parametrize("raw", ["1/0 dl vand", "0/0 stk æg", "1 1/0 dl mælk"])
def test_division_by_zero_in_ingredient_line_is_not_500(app, client, raw):
    c = safe(app, client)
    assert c.post("/api/parse", json={"lines": [raw]}).status_code == 200
    assert c.post("/api/recipes", json={"title": "x", "ingredients": [{"raw": raw}]}).status_code == 201


@pytest.mark.parametrize("raw", ["٣ dl mælk", "1,5,5 dl mælk", "1e308 g smør", "-5 g mel", "½ dl mælk", "1½ dl mælk",
                                 "1-2 dl mælk", "99999999999 dl mælk", "0 g sukker", "   ", "🍎", "x" * 300])
def test_odd_ingredient_lines_do_not_crash_parse(app, client, raw):
    c = safe(app, client)
    assert c.post("/api/parse", json={"lines": [raw]}).status_code == 200


def test_ingredient_line_over_300_chars_is_422(client):
    assert client.post("/api/recipes", json={"title": "x", "ingredients": [{"raw": "x" * 301}]}).status_code == 422


def test_blank_lines_are_dropped(client):
    r = client.post("/api/recipes", json={"title": "x", "ingredients": [{"raw": ""}, {"raw": "  "}, {"raw": "2 løg"}]}).json()
    assert [l["raw"] for l in r["ingredients"]] == ["2 løg"]


def test_negative_quantity_in_structured_line_is_rejected(client):
    r = client.post("/api/recipes", json={"title": "x", "ingredients": [
        {"raw": "x", "item": "x", "quantity": -5, "unit": "g"}]})
    assert r.status_code == 422


@pytest.mark.parametrize("servings", [0, -1, 101])
def test_servings_out_of_range(client, servings):
    assert client.post("/api/recipes", json={"title": "x", "servings": servings}).status_code == 422


def test_recipe_search_is_case_insensitive_for_danish_letters(client):
    client.post("/api/recipes", json={"title": "Æblegrød"})
    assert [r["title"] for r in client.get("/api/recipes", params={"q": "æble"}).json()] == ["Æblegrød"]
    assert [r["title"] for r in client.get("/api/recipes", params={"q": "ÆBLE"}).json()] == ["Æblegrød"]


def test_recipe_search_wildcards_are_literal(client):
    client.post("/api/recipes", json={"title": "Suppe"})
    assert client.get("/api/recipes", params={"q": "%"}).json() == []
    assert client.get("/api/recipes", params={"q": "_"}).json() == []


def test_update_with_foreign_ingredient_id_is_422(client):
    r = client.post("/api/recipes", json={"title": "x", "ingredients": [{"raw": "2 løg"}]}).json()
    body = {"title": "x", "ingredients": [{"raw": "2 løg", "item": "løg", "ingredient_id": 999999}]}
    assert client.put(f"/api/recipes/{r['id']}", json=body).status_code == 422


def test_recipe_delete_twice_is_404_second_time(client):
    r = client.post("/api/recipes", json={"title": "x"}).json()
    assert client.delete(f"/api/recipes/{r['id']}").status_code == 204
    assert client.delete(f"/api/recipes/{r['id']}").status_code == 404


def test_duplicate_source_url_across_slash_and_case(client):
    assert client.post("/api/recipes", json={"title": "a", "source_url": "https://ex.dk/Ret"}).status_code == 201
    assert client.post("/api/recipes", json={"title": "b", "source_url": "https://EX.dk/ret/"}).status_code == 409


# --- Billeder -----------------------------------------------------------------------------

@pytest.mark.parametrize("data", [PNG, JPG, b"RIFF\x00\x00\x00\x00WEBP" + b"0" * 32])
def test_image_formats_by_content(client, data):
    rid = client.post("/api/recipes", json={"title": "x"}).json()["id"]
    r = client.post(f"/api/recipes/{rid}/image", files={"file": ("x.bin", data, "application/octet-stream")})
    assert r.status_code == 200 and r.json()["image_url"]


@pytest.mark.parametrize("data", [b"", b"GIF89a....", b"<svg xmlns='http://www.w3.org/2000/svg'/>", b"%PDF-1.4", b"\x89PNG"])
def test_image_rejects_other_content_even_with_image_name(client, data):
    rid = client.post("/api/recipes", json={"title": "x"}).json()["id"]
    r = client.post(f"/api/recipes/{rid}/image", files={"file": ("x.png", data, "image/png")})
    assert r.status_code == 422


def test_image_replace_and_delete_removes_old_files(app, client):
    rid = client.post("/api/recipes", json={"title": "x"}).json()["id"]
    d = app.state.settings.image_dir
    client.post(f"/api/recipes/{rid}/image", files={"file": ("a.png", PNG, "image/png")})
    client.post(f"/api/recipes/{rid}/image", files={"file": ("a.jpg", JPG, "image/jpeg")})
    assert len(list(d.iterdir())) == 1
    client.delete(f"/api/recipes/{rid}")
    assert list(d.iterdir()) == []


def test_image_on_missing_recipe_is_404(client):
    assert client.post("/api/recipes/999/image", files={"file": ("a.png", PNG, "image/png")}).status_code == 404


@pytest.mark.parametrize("name", ["..%2F..%2Fetc%2Fpasswd", "%2e%2e%2fdata", ".hidden", "nonexistent.png", "a%5Cb"])
def test_image_path_traversal_is_404(client, name):
    assert client.get(f"/api/images/{name}").status_code == 404


# --- Påmindelser ---------------------------------------------------------------------------

@pytest.fixture
def meal(client):
    r = client.post("/api/recipes", json={"title": "x", "ingredients": [{"raw": "2 løg"}]}).json()
    p = client.post("/api/plans", json={"start_date": "2026-10-04"}).json()
    out = client.put(f"/api/plans/{p['id']}/slots", json={"date": "2026-10-05", "kind": "opskrift", "recipe_id": r["id"]}).json()
    return out["days"][1]["meal"]


@pytest.mark.parametrize("t", ["24:00", "7:00", "19:60", "19.00", "1900", "ab:cd", "19:00:00", "-1:00", ""])
def test_reminder_rejects_bad_times(client, meal, t):
    assert client.post(f"/api/meals/{meal['id']}/reminders", json={"text": "x", "first_time": t}).status_code == 422


@pytest.mark.parametrize("t", ["00:00", "23:59", "06:30"])
def test_reminder_accepts_valid_times(client, meal, t):
    r = client.post(f"/api/meals/{meal['id']}/reminders", json={"text": "x", "first_time": t, "again_time": t})
    assert r.status_code == 200
    got = r.json()["days"][1]["meal"]["reminders"][0]
    assert (got["first_time"], got["again_time"]) == (t, t)


def test_reminder_text_is_trimmed_emoji_kept_and_blank_rejected(client, meal):
    ok = client.post(f"/api/meals/{meal['id']}/reminders", json={"text": "  Kød   op 🥩 æøå  "})
    assert ok.json()["days"][1]["meal"]["reminders"][0]["text"] == "Kød op 🥩 æøå"
    assert client.post(f"/api/meals/{meal['id']}/reminders", json={"text": " \n "}).status_code == 422
    assert client.post(f"/api/meals/{meal['id']}/reminders", json={"text": "x" * 201}).status_code == 422


def test_reminder_follows_meal_on_move_and_dies_with_meal(client, meal):
    client.post(f"/api/meals/{meal['id']}/reminders", json={"text": "x"})
    moved = client.post(f"/api/meals/{meal['id']}/move", json={"date": "2026-10-07"}).json()
    assert len(moved["days"][3]["meal"]["reminders"]) == 1
    rid = moved["days"][3]["meal"]["reminders"][0]["id"]
    client.delete(f"/api/meals/{meal['id']}")
    assert client.patch(f"/api/reminders/{rid}", json={"done": True}).status_code == 404


def test_reminder_double_submit_makes_two_but_delete_is_idempotent_404(client, meal):
    for _ in range(2):
        out = client.post(f"/api/meals/{meal['id']}/reminders", json={"text": "x"}).json()
    rs = out["days"][1]["meal"]["reminders"]
    assert len(rs) == 2  # dokumenterer: ingen dublet-tjek (påmindelser må gerne ligne hinanden)
    assert client.delete(f"/api/reminders/{rs[0]['id']}").status_code == 200
    assert client.delete(f"/api/reminders/{rs[0]['id']}").status_code == 404


# --- Ingredienser og tjek ------------------------------------------------------------------

def test_ingredient_validation(client):
    assert client.post("/api/ingredients", json={"name": "", "department": "fg"}).status_code == 422
    assert client.post("/api/ingredients", json={"name": "x" * 101, "department": "fg"}).status_code == 422
    assert client.post("/api/ingredients", json={"name": "zzz", "department": "nej"}).status_code == 422
    assert client.post("/api/ingredients", json={"name": "zzz", "department": "fg", "grams_per_dl": 0}).status_code == 422
    assert client.post("/api/ingredients", json={"name": "zzz", "department": "fg", "grams_per_piece": -3}).status_code == 422


def test_ingredient_name_is_unique_case_and_alias_insensitive(client):
    assert client.post("/api/ingredients", json={"name": "LØG", "department": "fg"}).status_code == 409
    assert client.post("/api/ingredients", json={"name": "Kyllingebryst  ", "department": "kod"}).status_code in (201, 409)


def test_ingredient_update_404_and_rename_keeps_old_name_as_alias(app, client):
    make_system_admin(app)
    assert client.put("/api/ingredients/999999", json={"name": "x", "department": "fg"}).status_code == 404
    r = client.post("/api/ingredients", json={"name": "dragefrugt", "department": "fg"}).json()
    client.put(f"/api/ingredients/{r['id']}", json={"name": "pitaya", "department": "fg"})
    p = client.post("/api/parse", json={"lines": ["1 stk dragefrugt"]}).json()[0]
    assert p["ingredient"] and p["ingredient"]["name"] == "pitaya"


def test_confirm_and_ignore_on_missing_line_are_404(client):
    assert client.post("/api/lines/999999/confirm", json={"ingredient_id": 1}).status_code == 404
    assert client.post("/api/lines/999999/ignore").status_code == 404
    assert client.put("/api/lines/999999/main", json={"is_main": True}).status_code == 404


# --- Login ---------------------------------------------------------------------------------

@pytest.mark.parametrize("user", ["MAX", " max ", "Max"])
def test_login_username_is_case_and_space_insensitive(anon, user):
    assert anon.post("/api/login", json={"username": user, "password": PASSWORD}).status_code == 200


@pytest.mark.parametrize("body", [{}, {"username": "max"}, {"username": "x" * 51, "password": "a"},
                                  {"username": "max", "password": "x" * 201}, {"username": None, "password": None}])
def test_login_bad_bodies_are_422_not_500(anon, body):
    assert anon.post("/api/login", json=body).status_code == 422


def test_login_logout_roundtrip_and_cookie_is_httponly(anon):
    r = anon.post("/api/login", json={"username": "max", "password": PASSWORD})
    assert "httponly" in r.headers["set-cookie"].lower() and "samesite=lax" in r.headers["set-cookie"].lower()
    assert anon.get("/api/me").status_code == 200
    anon.post("/api/logout")
    assert anon.get("/api/me").status_code == 401
