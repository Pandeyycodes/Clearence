"""JWT auth + protected-route guarantees.

Runs against a throwaway SQLite DB (never the real clearance.db). The env vars
must be set BEFORE importing api.main, because db.session reads the DB URL and
main.py reads the demo credentials at import time.
"""
import os
import pathlib
import tempfile

_TMPDB = pathlib.Path(tempfile.gettempdir()) / "clearance_test_auth.db"
os.environ["CLEARANCE_DB_URL"] = f"sqlite:///{_TMPDB.as_posix()}"
os.environ["CLEARANCE_SECRET_KEY"] = "test-secret-key"
os.environ["CLEARANCE_DEMO_EMAIL"] = "recruiter@clearance.local"
os.environ["CLEARANCE_DEMO_PASSWORD"] = "demo1234"

import pytest
from fastapi.testclient import TestClient

from api.main import app
from db.session import engine

EMAIL = "recruiter@clearance.local"
PASSWORD = "demo1234"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:          # context manager triggers startup
        yield c
    # Release SQLite's file handle before deleting (required on Windows).
    engine.dispose()
    try:
        _TMPDB.unlink(missing_ok=True)
    except PermissionError:
        pass


def _token(client) -> str:
    r = client.post("/token", data={"username": EMAIL, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _auth(client) -> dict:
    return {"Authorization": f"Bearer {_token(client)}"}


# ------------------------------------------------------------------ login
def test_login_succeeds_with_correct_credentials(client):
    r = client.post("/token", data={"username": EMAIL, "password": PASSWORD})
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]


def test_login_fails_with_wrong_password(client):
    r = client.post("/token", data={"username": EMAIL, "password": "nope"})
    assert r.status_code == 401


# -------------------------------------------------------- route protection
def test_protected_route_rejects_without_token(client):
    assert client.get("/cases").status_code == 401


def test_protected_route_rejects_bad_token(client):
    r = client.get("/cases", headers={"Authorization": "Bearer garbage"})
    assert r.status_code == 401


def test_protected_route_accepts_valid_token(client):
    r = client.get("/cases", headers=_auth(client))
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_health_is_public(client):
    assert client.get("/health").status_code == 200


# ------------------------------------------------ audit trail records "who"
def test_screening_records_screened_by(client):
    resume = ("Senior accountant with ten years of experience in general "
              "ledger, financial reporting, auditing, and Excel modelling. "
              "Managed month-end close and reconciliations.")
    r = client.post(
        "/screen",
        data={"jd_text": "accountant general ledger auditing excel"},
        files={"file": ("resume.txt", resume.encode(), "text/plain")},
        headers=_auth(client),
    )
    assert r.status_code == 200, r.text
    assert r.json()["screened_by"] == EMAIL
