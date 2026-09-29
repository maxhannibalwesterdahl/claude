import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import pytest
from fastapi.testclient import TestClient

from madplan.api import create_app
from madplan.auth import hash_password
from madplan.config import Settings
from madplan.models import User

PASSWORD = "et-langt-kodeord"


@pytest.fixture
def app(tmp_path):
    return create_app(Settings(data_dir=tmp_path, secret="x" * 64, static_dir=None))


@pytest.fixture
def anon(app):
    with TestClient(app) as c:
        with app.state.db.sessionmaker() as s:
            s.add(User(username="max", password_hash=hash_password(PASSWORD)))
            s.commit()
        yield c


@pytest.fixture
def client(anon):
    r = anon.post("/api/login", json={"username": "Max", "password": PASSWORD})
    assert r.status_code == 200
    return anon


def ingredient_id(client, name):
    return next(i["id"] for i in client.get("/api/ingredients").json() if i["name"] == name)


