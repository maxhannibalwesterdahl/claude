"""Familier: påmindelser, push, migration af eksisterende data og kommandolinjen."""

import pytest
from alembic import command
from sqlalchemy import text

from conftest import PASSWORD, add_user, login
from madplan import cli
from madplan.db import alembic_config, make_engine, migrate
from test_reminders import ENDPOINT, START, Phone, at, plan, run, subscribe, thursday  # noqa: F401


@pytest.fixture
def other(app, client):
    add_user(app, "bea", "Familie B")
    return login(app, "bea")


# --- Påmindelser og push ------------------------------------------------------------

def test_reminders_only_go_to_own_familys_phones(app, client, other, plan):
    meal = thursday(plan)
    client.post(f"/api/meals/{meal['id']}/reminders", json={"text": "kød op"})
    mine, theirs = Phone(ENDPOINT), Phone("https://fcm.googleapis.com/fcm/send/anden-familie")
    subscribe(client, mine)
    subscribe(other, theirs)
    assert run(app, at(7, 19), mine) == 1
    assert len(mine.got) == 1 and theirs.got == []


def test_family_without_phones_does_not_block_others(app, client, other, plan):
    """Familie B har en telefon, men ingen påmindelser: intet sendes dertil."""
    meal = thursday(plan)
    client.post(f"/api/meals/{meal['id']}/reminders", json={"text": "kød op"})
    theirs = Phone("https://fcm.googleapis.com/fcm/send/anden-familie")
    subscribe(other, theirs)
    assert run(app, at(7, 19), theirs) == 0 and theirs.got == []
    # Først når familie A selv melder en telefon til, sendes der til den.
    mine = Phone(ENDPOINT)
    subscribe(client, mine)
    assert run(app, at(7, 20), mine) == 1 and theirs.got == []


def test_push_endpoint_cannot_be_taken_over_by_another_family(app, client, other, plan):
    meal = thursday(plan)
    client.post(f"/api/meals/{meal['id']}/reminders", json={"text": "kød op"})
    phone = Phone(ENDPOINT)
    subscribe(client, phone)
    r = other.post("/api/push/subscriptions", json={"endpoint": ENDPOINT, "keys": Phone(ENDPOINT).keys()})
    assert r.status_code == 409
    assert run(app, at(7, 19), phone) == 1      # abonnementet tilhører stadig familie A


def test_push_endpoint_can_move_between_users_in_same_family(app, client, plan):
    add_user(app, "anne", "Familie A", "medlem")
    phone = Phone(ENDPOINT)
    subscribe(client, phone)
    subscribe(login(app, "anne"), phone)


# --- Migration af eksisterende data -----------------------------------------------------

def _old_database(tmp_path):
    """En database i versionen før familier, med data som i drift."""
    url = f"sqlite:///{tmp_path / 'madplan.db'}"
    engine = make_engine(url)
    command.upgrade(alembic_config(url), "a3f7c0d9e512")
    with engine.begin() as c:
        c.execute(text("INSERT INTO user (id, username, password_hash, session_version, created_at) VALUES "
                       "(1, 'max', 'x', 1, '2026-01-01'), (2, 'anne', 'x', 3, '2026-01-01')"))
        c.execute(text("INSERT INTO ingredient (id, name, department, pantry) VALUES "
                       "(1, 'salt', 'tg', 1), (2, 'løg', 'fg', 0), (3, 'mel', 'tg', 1)"))
        c.execute(text("INSERT INTO recipe (id, title, instructions, child_note, created_at, updated_at) VALUES "
                       "(1, 'Suppe', '', 'uden chili', '2026-01-01', '2026-01-01'), "
                       "(2, 'Brød', '', '', '2026-01-01', '2026-01-01')"))
        c.execute(text("INSERT INTO plan (id, start_date, days, created_at) VALUES (1, '2026-10-26', 7, '2026-10-20')"))
        c.execute(text("INSERT INTO shopping_extra (id, plan_id, text, source, created_at, checked, updated_ms) "
                       "VALUES (1, 1, 'bleer', 'egen', '2026-10-20', 0, 0), (2, NULL, 'mælk', 'egen', '2026-10-20', 1, 5)"))
        c.execute(text("INSERT INTO setting (key, value) VALUES ('departments', '[\"fg\"]'), ('push_subject', 'https://x.ts.net')"))
        c.execute(text("INSERT INTO push_subscription (id, user_id, endpoint, p256dh, auth, created_at) "
                       "VALUES (1, 2, 'https://fcm.googleapis.com/a', 'k', 'a', '2026-10-20')"))
    return url, engine


def test_migration_moves_existing_data_to_family_1(tmp_path):
    url, engine = _old_database(tmp_path)
    assert migrate(engine, backup_dir=tmp_path / "backups") is True
    q = lambda sql: engine.connect().execute(text(sql)).all()  # noqa: E731
    assert q("SELECT id, name FROM household") == [(1, "Vores familie")]
    assert q("SELECT user_id, role FROM household_member ORDER BY user_id") == [(1, "admin"), (2, "admin")]
    assert q("SELECT id, household_id FROM plan") == [(1, 1)]
    assert q("SELECT id, household_id, plan_id, text, checked FROM shopping_extra ORDER BY id") == [
        (1, 1, 1, "bleer", 0), (2, 1, None, "mælk", 1)]
    assert q("SELECT id, created_by_household FROM recipe ORDER BY id") == [(1, 1), (2, 1)]
    assert q("SELECT ingredient_id FROM household_pantry WHERE household_id = 1 ORDER BY 1") == [(1,), (3,)]
    assert q("SELECT recipe_id, child_note FROM household_recipe_note") == [(1, "uden chili")]
    assert q("SELECT household_id, key FROM setting ORDER BY key") == [(1, "departments"), (0, "push_subject")]
    assert q("SELECT user_id FROM push_subscription") == [(2,)]
    assert q("SELECT is_system_admin FROM user ORDER BY id") == [(0,), (0,)]
    assert q("SELECT COUNT(*) FROM household_ingredient_pref")[0][0] == q("SELECT COUNT(*) FROM household_line_match")[0][0] == 0
    assert q("PRAGMA foreign_key_check") == []
    assert len(list((tmp_path / "backups").glob("premigrate-*.db"))) == 1


def test_migrated_database_works_in_the_app(tmp_path):
    """Appen starter på den migrerede database; en eksisterende bruger ser sine data."""
    from fastapi.testclient import TestClient

    from madplan.api import create_app
    from madplan.auth import hash_password
    from madplan.config import Settings

    _, engine = _old_database(tmp_path)
    engine.dispose()
    app = create_app(Settings(data_dir=tmp_path, secret="x" * 64, static_dir=None))
    with TestClient(app) as c:
        with app.state.db.sessionmaker() as s:
            s.execute(text("UPDATE user SET password_hash = :h WHERE id = 1"), {"h": hash_password(PASSWORD)})
            s.commit()
        assert c.post("/api/login", json={"username": "max", "password": PASSWORD}).json()["household"]["name"] == "Vores familie"
        assert c.get("/api/plans").json()[0]["id"] == 1
        recipes = {r["title"]: r for r in c.get("/api/recipes").json()}
        assert recipes["Suppe"]["owned"] is True
        assert c.get(f"/api/recipes/{recipes['Suppe']['id']}").json()["child_note"] == "uden chili"
        salt = next(i for i in c.get("/api/ingredients").json() if i["name"] == "salt")
        assert salt["pantry"] is True
        assert [i["name"] for i in c.get("/api/shopping?plan_id=1").json()["items"]] == ["bleer"]   # mælk er købt for længe siden
        assert [d["code"] for d in c.get("/api/settings/departments").json()][0] == "fg"


def test_migration_of_empty_database_creates_no_family(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'madplan.db'}")
    migrate(engine)
    assert engine.connect().execute(text("SELECT COUNT(*) FROM household")).scalar() == 0


def test_downgrade_roundtrip_keeps_data(tmp_path):
    url, engine = _old_database(tmp_path)
    migrate(engine)
    engine.dispose()
    command.downgrade(alembic_config(url), "a3f7c0d9e512")
    engine = make_engine(url)
    with engine.connect() as c:
        assert c.execute(text("SELECT COUNT(*) FROM plan")).scalar() == 1
        assert c.execute(text("SELECT key FROM setting ORDER BY key")).all() == [("departments",), ("push_subject",)]


# --- Kommandolinjen -----------------------------------------------------------------------

@pytest.fixture
def cli_env(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("APP_SECRET", "x" * 64)
    monkeypatch.setattr(cli, "_ask_password", lambda: PASSWORD)
    return tmp_path


def test_cli_creates_family_and_users(cli_env, capsys):
    assert cli.main(["create-household", "Familien Hansen"]) == 0
    assert cli.main(["create-household", "Familien Berg"]) == 0
    # To familier: familien skal angives.
    assert cli.main(["create-user", "kim"]) == 1
    assert cli.main(["create-user", "kim", "--household", "familien hansen"]) == 0
    assert cli.main(["create-user", "lis", "--household", "2", "--medlem"]) == 0
    assert cli.main(["create-user", "kim", "--household", "2"]) == 1       # findes allerede
    assert cli.main(["set-system-admin", "kim"]) == 0
    assert cli.main(["set-system-admin", "findes-ikke"]) == 1
    capsys.readouterr()
    cli.main(["list-users"])
    out = capsys.readouterr().out
    assert "kim [Familien Hansen, admin] [systemadmin]" in out
    assert "lis [Familien Berg, medlem]" in out
    cli.main(["set-system-admin", "kim", "--fjern"])
    cli.main(["list-households"])
    out = capsys.readouterr().out
    assert "Familien Hansen\tkim" in out and "Familien Berg\tlis" in out
    cli.main(["list-users"])
    assert "systemadmin" not in capsys.readouterr().out


def test_cli_new_family_gets_the_starter_pantry(cli_env):
    from sqlalchemy import select

    from madplan.models import HouseholdPantry, Ingredient
    cli.main(["create-household", "Ny familie"])
    engine = make_engine(f"sqlite:///{cli_env / 'madplan.db'}")
    with engine.connect() as c:
        got = {r[0] for r in c.execute(select(HouseholdPantry.ingredient_id).where(HouseholdPantry.household_id == 1))}
        starter = {r[0] for r in c.execute(select(Ingredient.id).where(Ingredient.pantry.is_(True)))}
    assert got == starter and len(got) > 10


def test_cli_single_family_is_default(cli_env):
    cli.main(["create-household", "Alene"])
    assert cli.main(["create-user", "kim"]) == 0
