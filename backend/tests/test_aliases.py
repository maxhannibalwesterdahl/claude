"""Alias-læring må aldrig i stilhed omdøbe varer på tværs af opskrifter.
Fejlene her blev fundet i en gennemgang og genskabt, før de blev rettet."""

from conftest import ingredient_id
from sqlalchemy import select

from madplan.catalog import Catalog, sync_seed
from madplan.models import Ingredient, IngredientAlias


def recipe(client, title, lines):
    return client.post("/api/recipes", json={"title": title, "ingredients": [{"raw": l} for l in lines]}).json()


def line_of(client, rec_id, n=0):
    return client.get(f"/api/recipes/{rec_id}").json()["ingredients"][n]


def parse(client, text):
    return client.post("/api/parse", json={"lines": [text]}).json()[0]["ingredient"]["name"]


def test_confirming_a_name_as_another_ingredient_stays_local(client):
    a = recipe(client, "A", ["2 løg"])
    b = recipe(client, "B", ["1 løg"])
    rodlog = ingredient_id(client, "rødløg")
    r = client.post(f"/api/lines/{a['ingredients'][0]['id']}/confirm", json={"ingredient_id": rodlog})
    assert r.json() == {"also_updated": 0}
    # Kun linjen i A er rødløg. B og nye opskrifter bruger stadig "løg".
    assert line_of(client, a["id"])["ingredient"]["name"] == "rødløg"
    assert line_of(client, b["id"])["ingredient"]["name"] == "løg"
    assert parse(client, "3 løg") == "løg"
    # Varen "løg" kan stadig redigeres.
    log = ingredient_id(client, "løg")
    assert client.put(f"/api/ingredients/{log}", json={"name": "løg", "department": "fg"}).status_code == 200


def test_old_bad_alias_is_ignored_and_can_be_undone(app, client):
    # Data fra før rettelsen: et bruger-alias "løg" -> rødløg.
    with app.state.db.sessionmaker() as s:
        rod = s.scalar(select(Ingredient).where(Ingredient.name == "rødløg"))
        s.add(IngredientAlias(alias="løg", key="løg", ingredient=rod, source="user"))
        s.commit()
    assert parse(client, "2 løg") == "løg"  # ignoreres: navnet tilhører en anden vare
    a = recipe(client, "A", ["2 løg"])
    client.post(f"/api/lines/{a['ingredients'][0]['id']}/confirm", json={"ingredient_id": ingredient_id(client, "løg")})
    with app.state.db.sessionmaker() as s:
        assert s.scalar(select(IngredientAlias).where(IngredientAlias.key == "løg")) is None


def test_saving_a_recipe_does_not_relearn_old_confirmations(client):
    d = recipe(client, "D", ["2 dl fløde"])
    e = recipe(client, "E", ["1 dl fløde"])
    f = recipe(client, "F", ["3 dl fløde"])
    # "fløde" er ikke et varenavn, så bekræftelser bliver til aliaser.
    client.post(f"/api/lines/{d['ingredients'][0]['id']}/confirm", json={"ingredient_id": ingredient_id(client, "piskefløde")})
    client.post(f"/api/lines/{e['ingredients'][0]['id']}/confirm", json={"ingredient_id": ingredient_id(client, "madlavningsfløde")})
    assert line_of(client, f["id"])["ingredient"]["name"] == "madlavningsfløde"
    # Gem D igen (kun titlen ændret): F må ikke skifte tilbage.
    rec = client.get(f"/api/recipes/{d['id']}").json()
    body = {"title": "D2", "ingredients": [
        {k: v for k, v in l.items() if k != "ingredient"} | {"ingredient_id": l["ingredient"]["id"]} for l in rec["ingredients"]]}
    assert client.put(f"/api/recipes/{d['id']}", json=body).status_code == 200
    assert line_of(client, f["id"])["ingredient"]["name"] == "madlavningsfløde"


def test_seed_alias_colliding_with_user_ingredient_does_not_crash(app, client, monkeypatch):
    client.post("/api/ingredients", json={"name": "hytteost light", "department": "mej"})
    # En senere udgave af startdata tilføjer samme navn som alias til hytteost.
    from madplan.ingredients import matcher as m
    real = m.load_table
    monkeypatch.setattr(m, "load_table", lambda text=None: [
        m.Ingredient(i.name, i.department, i.pantry, i.aliases + (("hytteost light",) if i.name == "hytteost" else ()))
        for i in real(text)])
    with app.state.db.sessionmaker() as s:
        sync_seed(s)
        Catalog(s)  # må ikke kaste
    assert parse(client, "200 g hytteost light") == "hytteost light"


def test_catalog_skips_conflicting_rows_instead_of_raising(app, client):
    with app.state.db.sessionmaker() as s:
        skyr = s.scalar(select(Ingredient).where(Ingredient.name == "skyr"))
        # Et startalias, der er lig navnet på en anden vare (kan opstå ved gamle data).
        s.add(IngredientAlias(alias="kvark", key="kvark", ingredient=skyr, source="seed"))
        s.commit()
        Catalog(s)
    assert parse(client, "250 g kvark") == "kvark"
