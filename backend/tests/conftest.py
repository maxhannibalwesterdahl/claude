import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import pytest
from fastapi.testclient import TestClient

from madplan.api import create_app
from madplan.auth import hash_password
from madplan.config import Settings
from madplan.households import add_member, create_household
from madplan.models import Household, User

PASSWORD = "et-langt-kodeord"


def add_user(app, username: str, household: str | int, role: str = "admin") -> int:
    """Bruger i en familie (oprettes, hvis navnet er ukendt). Returnerer familiens id."""
    with app.state.db.sessionmaker() as s:
        if isinstance(household, int):
            h = s.get(Household, household)
        else:
            h = s.query(Household).filter_by(name=household).one_or_none() or create_household(s, household)
        user = User(username=username, password_hash=hash_password(PASSWORD))
        s.add(user)
        s.flush()
        add_member(s, h, user, role)
        s.commit()
        return h.id


def make_system_admin(app, username: str = "max") -> None:
    with app.state.db.sessionmaker() as s:
        s.query(User).filter_by(username=username).one().is_system_admin = True
        s.commit()


def login(app, username: str) -> TestClient:
    c = TestClient(app)
    assert c.post("/api/login", json={"username": username, "password": PASSWORD}).status_code == 200
    return c


@pytest.fixture
def app(tmp_path):
    return create_app(Settings(data_dir=tmp_path, secret="x" * 64, static_dir=None))


@pytest.fixture
def anon(app):
    with TestClient(app) as c:
        add_user(app, "max", "Familie A")
        yield c


@pytest.fixture
def client(anon):
    r = anon.post("/api/login", json={"username": "Max", "password": PASSWORD})
    assert r.status_code == 200
    return anon


def ingredient_id(client, name):
    return next(i["id"] for i in client.get("/api/ingredients").json() if i["name"] == name)


