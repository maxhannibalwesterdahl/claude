import json

import pytest
from conftest import PASSWORD, ingredient_id
from sqlalchemy import select

from madplan import importer
from madplan.models import IngredientAlias, User


# --- Login ------------------------------------------------------------------

def test_api_requires_login(anon):
    assert anon.get("/api/recipes").status_code == 401
    assert anon.get("/api/me").status_code == 401


def test_wrong_password_and_unknown_user(anon):
    assert anon.post("/api/login", json={"username": "max", "password": "forkert"}).status_code == 401
    assert anon.post("/api/login", json={"username": "ukendt", "password": PASSWORD}).status_code == 401


def test_login_is_rate_limited(anon):
    codes = [anon.post("/api/login", json={"username": "max", "password": "forkert"},
                       headers={"x-forwarded-for": "9.9.9.9"}).status_code for _ in range(6)]
    assert codes == [401] * 5 + [429]
    # En anden IP er ikke ramt.
    r = anon.post("/api/login", json={"username": "max", "password": PASSWORD}, headers={"x-forwarded-for": "8.8.8.8"})
    assert r.status_code == 200


def test_rate_limit_uses_address_set_by_proxy(anon):
    # Klienten kan selv skrive forreste adresser i X-Forwarded-For. Den sidste
    # (sat af Tailscale) er den samme, så grænsen rammer stadig.
    codes = [anon.post("/api/login", json={"username": "max", "password": "forkert"},
                       headers={"x-forwarded-for": f"10.0.0.{i}, 7.7.7.7"}).status_code for i in range(6)]
    assert codes == [401] * 5 + [429]


def test_successful_login_does_not_count_as_attempt(anon):
    h = {"x-forwarded-for": "5.5.5.5"}
    for _ in range(4):
        anon.post("/api/login", json={"username": "max", "password": "forkert"}, headers=h)
    assert anon.post("/api/login", json={"username": "max", "password": PASSWORD}, headers=h).status_code == 200
    # 4 fejl + 1 succes: der er stadig ét forsøg tilbage.
    assert anon.post("/api/login", json={"username": "max", "password": "forkert"}, headers=h).status_code == 401


def test_login_is_refused_when_hash_gate_is_full(anon):
    from madplan.auth import HASH_GATE
    HASH_GATE.acquire(); HASH_GATE.acquire()
    try:
        r = anon.post("/api/login", json={"username": "max", "password": PASSWORD}, headers={"x-forwarded-for": "6.6.6.6"})
        assert r.status_code == 429
    finally:
        HASH_GATE.release(); HASH_GATE.release()
    assert anon.post("/api/login", json={"username": "max", "password": PASSWORD}).status_code == 200


def test_new_password_logs_out_old_sessions(app, client):
    assert client.get("/api/me").json()["username"] == "max"
    with app.state.db.sessionmaker() as s:
        s.scalar(select(User)).session_version += 1
        s.commit()
    assert client.get("/api/me").status_code == 401


def test_logout(client):
    client.post("/api/logout")
    assert client.get("/api/me").status_code == 401


# --- Opskrifter ---------------------------------------------------------------

def test_create_recipe_parses_lines_and_suggests_main(client):
    r = client.post("/api/recipes", json={
        "title": "Kødsovs",
        "servings": 4,
        "instructions": ["Brun kødet.", "  Tilsæt   tomater. ", ""],
        "ingredients": [
            {"raw": "500 g hakket oksekød"},
            {"raw": "2 løg, finthakket"},
            {"raw": "2 dåser hakkede tomater"},
            {"raw": "salt og peber"},
            {"raw": "1 stk dragefrugt"},
        ],
    })
    assert r.status_code == 201, r.text
    rec = r.json()
    assert rec["instructions"] == ["Brun kødet.", "Tilsæt tomater."]
    lines = rec["ingredients"]
    assert [l["item"] for l in lines] == ["hakket oksekød", "løg", "hakkede tomater", "salt og peber", "dragefrugt"]
    assert lines[1]["quantity"] == 2 and lines[1]["note"] == "finthakket"
    assert lines[0]["ingredient"]["name"] == "hakket oksekød"
    assert lines[4]["ingredient"] is None and lines[4]["match_status"] == "ingen"
    assert [l["is_main"] for l in lines] == [True, False, False, False, False]

    summary = client.get("/api/recipes").json()
    assert summary[0]["main_ingredients"] == ["hakket oksekød"]
    assert summary[0]["to_review"] == 1
    assert client.get("/api/recipes?q=sovs").json()[0]["title"] == "Kødsovs"
    assert client.get("/api/recipes?q=kage").json() == []


def test_main_without_meat_is_heaviest(client):
    rec = client.post("/api/recipes", json={"title": "Grøntsagssuppe", "ingredients": [
        {"raw": "2 gulerødder"}, {"raw": "1 blomkål"}, {"raw": "1 løg"}, {"raw": "1 l vand"},
    ]}).json()
    assert [l["item"] for l in rec["ingredients"] if l["is_main"]] == ["blomkål"]


def test_update_keeps_line_ids_and_learns_confirmed_items(client):
    rec = client.post("/api/recipes", json={"title": "A", "ingredients": [
        {"raw": "1 dragefrugt"}, {"raw": "2 løg"},
    ]}).json()
    other = client.post("/api/recipes", json={"title": "B", "ingredients": [{"raw": "2 dragefrugter"}]}).json()
    first, second = rec["ingredients"]
    mango = ingredient_id(client, "mango")

    body = {"title": "A", "ingredients": [
        {**first, "ingredient_id": mango, "match_status": "bekræftet"},
        {"raw": "3 gulerødder"},  # ny linje
    ]}
    body["ingredients"][0].pop("ingredient")
    r = client.put(f"/api/recipes/{rec['id']}", json=body)
    assert r.status_code == 200, r.text
    lines = r.json()["ingredients"]
    assert lines[0]["id"] == first["id"]
    assert lines[0]["ingredient"]["name"] == "mango" and lines[0]["match_status"] == "bekræftet"
    assert second["id"] not in [l["id"] for l in lines]
    assert lines[1]["item"] == "gulerødder" and lines[1]["ingredient"]["name"] == "gulerod"

    # "dragefrugt" er lært; flertalsformen i opskrift B rettes kun, hvis nøglen er den samme.
    assert client.post("/api/parse", json={"lines": ["1 dragefrugt"]}).json()[0]["ingredient"]["name"] == "mango"
    assert client.get(f"/api/recipes/{other['id']}").json()["ingredients"][0]["match_status"] == "ingen"


@pytest.mark.parametrize("url", ["javascript:alert(1)", " JavaScript:alert(1)", "data:text/html,x", "ftp://x.dk"])
def test_source_url_must_be_http(client, url):
    assert client.post("/api/recipes", json={"title": "A", "source_url": url}).status_code == 422


def test_source_url_http_is_accepted(client):
    r = client.post("/api/recipes", json={"title": "A", "source_url": "https://www.valdemarsro.dk/lasagne/"})
    assert r.status_code == 201
    assert client.post("/api/recipes", json={"title": "B", "source_url": ""}).status_code == 201


def test_line_from_other_recipe_is_rejected(client):
    a = client.post("/api/recipes", json={"title": "A", "ingredients": [{"raw": "1 løg"}]}).json()
    b = client.post("/api/recipes", json={"title": "B", "ingredients": []}).json()
    line = a["ingredients"][0]
    r = client.put(f"/api/recipes/{b['id']}", json={"title": "B", "ingredients": [{"id": line["id"], "raw": "x"}]})
    assert r.status_code == 422


def test_review_confirm_updates_all_recipes(client):
    for title in ("A", "B"):
        client.post("/api/recipes", json={"title": title, "ingredients": [{"raw": "2 spsk vaniljeskyr"}]})
    review = client.get("/api/review").json()
    assert [(l["recipe_title"], l["match_status"]) for l in review] == [("A", "usikker"), ("B", "usikker")]

    r = client.post(f"/api/lines/{review[0]['id']}/confirm", json={"ingredient_id": ingredient_id(client, "skyr")})
    assert r.json() == {"also_updated": 1}
    assert client.get("/api/review").json() == []


def test_set_main_on_several_lines(client):
    rec = client.post("/api/recipes", json={"title": "A", "ingredients": [
        {"raw": "500 g hakket oksekød"}, {"raw": "200 g bacon"}, {"raw": "2 løg"}]}).json()
    assert [l["is_main"] for l in rec["ingredients"]] == [True, True, False]
    for line in rec["ingredients"][1:]:
        assert client.put(f"/api/lines/{line['id']}/main", json={"is_main": line["item"] == "løg"}).status_code == 200
    rec = client.get(f"/api/recipes/{rec['id']}").json()
    assert [l["is_main"] for l in rec["ingredients"]] == [True, False, True]
    assert client.put("/api/lines/9999/main", json={"is_main": True}).status_code == 404


def test_ignore_line(client):
    client.post("/api/recipes", json={"title": "A", "ingredients": [{"raw": "pynt efter smag"}]})
    line = client.get("/api/review").json()[0]
    client.post(f"/api/lines/{line['id']}/ignore")
    assert client.get("/api/review").json() == []


def test_delete_recipe(client):
    rec = client.post("/api/recipes", json={"title": "A", "ingredients": [{"raw": "1 løg"}]}).json()
    assert client.delete(f"/api/recipes/{rec['id']}").status_code == 204
    assert client.get(f"/api/recipes/{rec['id']}").status_code == 404


# --- Import -------------------------------------------------------------------

RECIPE_HTML = """<html><head><script type="application/ld+json">{}</script></head><body></body></html>""".format(
    json.dumps({
        "@context": "https://schema.org",
        "@type": "Recipe",
        "name": "Lasagne med kødsovs",
        "recipeYield": "4 personer",
        "image": "https://opskrifter.example/lasagne.jpg",
        "recipeIngredient": ["500 g hakket oksekød", "1 dåse hakkede tomater", "9 lasagneplader", "125 g mozzarella"],
        "recipeInstructions": [
            {"@type": "HowToStep", "text": "Lav kødsovsen."},
            {"@type": "HowToStep", "text": "Byg lasagnen og bag den."},
        ],
    })
)


@pytest.fixture
def fake_web(monkeypatch, tmp_path):
    monkeypatch.setattr(importer, "check_url", lambda url: url)
    monkeypatch.setattr(importer, "fetch", lambda url: RECIPE_HTML)

    def download(url, image_dir):
        image_dir.mkdir(parents=True, exist_ok=True)
        (image_dir / "abc.jpg").write_bytes(b"jpeg")
        return "abc.jpg"

    monkeypatch.setattr(importer, "download_image", download)


def test_import_recipe(client, fake_web):
    url = "https://opskrifter.example/lasagne"
    r = client.post("/api/recipes/import", json={"url": url})
    assert r.status_code == 201, r.text
    rec = r.json()
    assert rec["title"] == "Lasagne med kødsovs"
    assert rec["servings"] == 4
    assert rec["instructions"] == ["Lav kødsovsen.", "Byg lasagnen og bag den."]
    assert rec["source_url"] == url
    assert [l["ingredient"]["name"] for l in rec["ingredients"]] == [
        "hakket oksekød", "hakkede tomater", "lasagneplader", "mozzarella"]
    assert [l["is_main"] for l in rec["ingredients"]] == [True, False, False, False]
    assert client.get(rec["image_url"]).content == b"jpeg"

    dup = client.post("/api/recipes/import", json={"url": url})
    assert dup.status_code == 409 and dup.json()["detail"]["id"] == rec["id"]


def test_import_page_without_recipe(client, monkeypatch):
    monkeypatch.setattr(importer, "check_url", lambda url: url)
    monkeypatch.setattr(importer, "fetch", lambda url: "<html><body>Ingen opskrift</body></html>")
    r = client.post("/api/recipes/import", json={"url": "https://opskrifter.example/artikel"})
    assert r.status_code == 422
    assert "opskrift" in r.json()["detail"]


@pytest.mark.parametrize("url", ["ftp://x.dk/a", "http://localhost/x", "http://192.168.1.68:8006/", "http://10.0.0.1/"])
def test_import_refuses_local_addresses(url):
    with pytest.raises(importer.RecipeImportError):
        importer.check_url(url)


def test_images_require_login(anon):
    assert anon.get("/api/images/abc.jpg").status_code == 401


# --- Ingredienser -------------------------------------------------------------

def test_seed_has_conversions(client):
    ings = {i["name"]: i for i in client.get("/api/ingredients").json()}
    assert len(ings) > 200
    assert ings["løg"]["grams_per_piece"] == 150
    assert ings["hvedemel"]["grams_per_dl"] == 60 and ings["hvedemel"]["pantry"]
    assert "oksefars" in ings["hakket oksekød"]["aliases"]


def test_create_and_rename_ingredient(app, client):
    r = client.post("/api/ingredients", json={"name": "Dragefrugt", "department": "fg"})
    assert r.status_code == 201 and r.json()["name"] == "dragefrugt"
    assert client.post("/api/ingredients", json={"name": "dragefrugt", "department": "fg"}).status_code == 409
    # Et navn, der allerede er alias for en anden vare, afvises.
    assert client.post("/api/ingredients", json={"name": "oksefars", "department": "kod"}).status_code == 409

    løg = ingredient_id(client, "løg")
    r = client.put(f"/api/ingredients/{løg}", json={"name": "gule løg", "department": "fg", "grams_per_piece": 140})
    assert r.status_code == 200, r.text
    assert client.post("/api/parse", json={"lines": ["2 løg"]}).json()[0]["ingredient"]["name"] == "gule løg"

    # Genstart: startdata lægger ikke "løg" ind igen.
    from madplan.catalog import sync_seed
    with app.state.db.sessionmaker() as s:
        assert sync_seed(s) == 0
        assert s.scalar(select(IngredientAlias).where(IngredientAlias.key == "løg")).source == "user"


def test_new_ingredient_is_matched_in_existing_recipes(client):
    rec = client.post("/api/recipes", json={"title": "A", "ingredients": [{"raw": "2 dragefrugter"}]}).json()
    assert rec["ingredients"][0]["match_status"] == "ingen"
    client.post("/api/ingredients", json={"name": "dragefrugt", "department": "fg"})
    line = client.get(f"/api/recipes/{rec['id']}").json()["ingredients"][0]
    assert (line["ingredient"]["name"], line["match_status"]) == ("dragefrugt", "sikker")


def test_meta(client):
    meta = client.get("/api/meta").json()
    assert {"code": "kod", "name": "Kød & fisk"} in meta["departments"]
    assert "dl" in meta["units"]


def test_unknown_api_route_is_json_404(client):
    r = client.get("/api/findes-ikke")
    assert r.status_code == 404 and r.json()["detail"] == "Findes ikke"


def test_backup_keeps_newest_copies(app, client, tmp_path):
    from datetime import date

    from madplan.cli import backup

    client.post("/api/recipes", json={"title": "Kødsovs", "ingredients": [{"raw": "1 løg"}]})
    for day in range(1, 5):
        backup(tmp_path, keep=2, today=date(2026, 10, day))
    copies = sorted(p.name for p in (tmp_path / "backups").iterdir())
    assert copies == ["madplan-2026-10-03.db", "madplan-2026-10-04.db"]
    import sqlite3
    con = sqlite3.connect(tmp_path / "backups" / copies[-1])
    assert con.execute("select title from recipe").fetchall() == [("Kødsovs",)]
    con.close()
