"""Tests for offline-spiken: login, synkronisering og en browser-test med to
"telefoner", hvor den ene er offline."""

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("APP_SECRET", "x" * 40)
os.environ.setdefault("APP_PASSWORD", "hemmelig")

import app as spike  # noqa: E402


@pytest.fixture()
def client(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    monkeypatch.setenv("DB_PATH", str(tmp_path / "t.db"))
    spike._attempts.clear()
    with TestClient(spike.app) as c:
        yield c


def login(c, password="hemmelig"):
    return c.post("/login", data={"password": password}, follow_redirects=False)


def test_session_expires_and_rejects_tampering():
    s = spike.make_session(now=1000)
    assert spike.valid_session(s, now=1001)
    assert not spike.valid_session(s, now=1000 + 91 * 86400)
    assert not spike.valid_session(s.replace(".", ".0"), now=1001)
    assert not spike.valid_session(None)


def test_api_requires_login(client):
    assert client.post("/api/sync", json={"changes": []}).status_code == 401


def test_wrong_password_and_rate_limit(client):
    assert "Forkert" in login(client, "forkert").headers["location"]
    for _ in range(5):
        login(client, "forkert")
    assert "mange" in login(client, "hemmelig").headers["location"]


def test_last_write_wins(client):
    assert login(client).status_code == 303
    client.post("/api/sync", json={"changes": [{"id": 1, "checked": True, "ts": 2000}]})
    # En ældre ændring (fx fra en telefon, der var offline) må ikke overskrive.
    items = client.post("/api/sync", json={"changes": [{"id": 1, "checked": False, "ts": 1000}]}).json()["items"]
    assert items[0]["checked"] is True


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture()
def server(tmp_path):
    port = _free_port()
    env = os.environ | {"DB_PATH": str(tmp_path / "e2e.db")}
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app:app", "--port", str(port)],
        cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"
    for _ in range(50):
        try:
            socket.create_connection(("127.0.0.1", port), timeout=0.1).close()
            break
        except OSError:
            time.sleep(0.1)
    yield base
    proc.terminate()
    proc.wait()


def test_offline_phone_syncs_when_back_online(server):
    pw = pytest.importorskip("playwright.sync_api")
    with pw.sync_playwright() as p:
        # CHROMIUM_PATH: brug en allerede installeret Chromium i stedet for
        # Playwrights egen (fx i CI eller et sandkassemiljø).
        exe = os.environ.get("CHROMIUM_PATH")
        browser = p.chromium.launch(executable_path=exe) if exe else p.chromium.launch()

        def phone():
            ctx = browser.new_context(viewport={"width": 390, "height": 844})
            page = ctx.new_page()
            page.goto(server + "/login")
            page.fill("input[name=password]", "hemmelig")
            page.click("button[type=submit]")
            page.wait_for_selector("text=Synkroniseret")
            return ctx, page

        ctx1, p1 = phone()
        ctx2, p2 = phone()
        # Vent til service workeren har gemt app-skallen.
        p1.wait_for_function("navigator.serviceWorker.controller !== null || navigator.serviceWorker.ready")
        p1.reload()
        p1.wait_for_selector("text=Synkroniseret")

        # Telefon 1 mister dækning i butikken.
        ctx1.set_offline(True)
        p1.reload()  # åbnes igen uden net: skal komme fra cache
        p1.wait_for_selector("text=Løg (3 stk)")
        p1.check("label:has-text('Løg (3 stk)') input")
        p1.check("label:has-text('Bleer') input")
        p1.wait_for_selector("text=Offline – 2 ændringer venter")

        # Telefon 2 er online og ser endnu intet.
        p2.reload()
        p2.wait_for_selector("text=Synkroniseret")
        assert not p2.is_checked("label:has-text('Løg (3 stk)') input")

        # Dækning igen.
        ctx1.set_offline(False)
        p1.evaluate("window.dispatchEvent(new Event('online'))")
        p1.wait_for_selector("text=Synkroniseret")

        p2.reload()
        p2.wait_for_selector("text=Synkroniseret")
        assert p2.is_checked("label:has-text('Løg (3 stk)') input")
        assert p2.is_checked("label:has-text('Bleer') input")
        browser.close()
