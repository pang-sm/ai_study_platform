import os
import sys
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


TEST_ROOT = Path(tempfile.mkdtemp(prefix="ai-study-platform-tests-"))
os.environ["DATABASE_URL"] = f"sqlite:///{(TEST_ROOT / 'test.db').as_posix()}"
os.environ["UPLOAD_ROOT"] = str(TEST_ROOT / "uploads")

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import database  # noqa: E402
import main  # noqa: E402


@pytest.fixture
def client():
    with TestClient(main.app) as test_client:
        yield test_client


@pytest.fixture
def db_session():
    session = database.SessionLocal()
    try:
        yield session
    finally:
        session.close()


def register_and_login(test_client: TestClient, username: str, password: str = "secret123"):
    register = test_client.post("/register", json={"username": username, "password": password})
    assert register.status_code == 200, register.text
    login = test_client.post("/login", json={"username": username, "password": password})
    assert login.status_code == 200, login.text
    assert "ai_session" in test_client.cookies
    return login.json()["user"]
