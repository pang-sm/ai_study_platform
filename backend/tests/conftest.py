import os
import sys
import tempfile
from datetime import timezone
from unittest.mock import patch
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


TEST_ROOT = Path(tempfile.mkdtemp(prefix="ai-study-platform-tests-"))
os.environ["DATABASE_URL"] = f"sqlite:///{(TEST_ROOT / 'test.db').as_posix()}"
os.environ["UPLOAD_ROOT"] = str(TEST_ROOT / "uploads")
# STEP 7A: tests exercise the SHADOW (INTERNAL) pipeline by default; production stays OFF.
os.environ["STUDENT_TWIN_MODE"] = "internal"

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import database  # noqa: E402
import main  # noqa: E402
import models  # noqa: E402
from usage.models import Subscription  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_provider_health():
    """Router V1 availability state is PROCESS-global; a test must not leak it into the next.

    One test degrading a model (three provider failures) would otherwise change which model a
    later test's router selects — a suite that passes or fails depending on test order. The
    registry itself is untouched: this only clears the outcomes recorded during a test.
    """
    from ai.health import registry
    registry().reset()
    yield
    registry().reset()


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


def grant_unified_tier(db, username: str, tier: str, days: int = 30) -> None:
    """TEST ONLY: grant a unified subscription tier — the ONE thing that opens a feature.

    ACCEL_PRODUCT_S10 made the unified tier the single membership authority, so a test that
    wants a paid product feature must grant the TIER. Writing only a
    ``user_service_memberships`` row records a plan and opens nothing, which is asserted
    directly in ``test_feature_entitlements.py``.
    """
    from datetime import datetime, timedelta

    user = db.query(models.User).filter(models.User.username == username).one()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    db.query(Subscription).filter(
        Subscription.user_id == user.id, Subscription.status == "active",
    ).update({"status": "cancelled", "updated_at": now})
    db.add(Subscription(
        user_id=user.id, tier=tier, status="active", start_at=now,
        end_at=now + timedelta(days=days) if days else None,
        source="test", created_at=now, updated_at=now))
    db.commit()


def register_and_login(test_client: TestClient, username: str, password: str = "secret123"):
    """TEST ONLY: establish a verified registration proof through public routes."""
    email = f"{username}@example.test"
    sent_codes: list[str] = []

    def capture_test_email(_recipient: str, code: str) -> bool:
        sent_codes.append(code)
        return True

    with patch.object(main, "_send_email_code", side_effect=capture_test_email):
        sent = test_client.post("/auth/register/send-code", json={"email": email})
        assert sent.status_code == 200, sent.text
        verified = test_client.post("/auth/register/verify-code", json={"email": email, "code": sent_codes[-1]})
        assert verified.status_code == 200, verified.text
    register = test_client.post("/register", json={"username": username, "password": password, "email": email})
    assert register.status_code == 200, register.text
    login = test_client.post("/login", json={"username": username, "password": password})
    assert login.status_code == 200, login.text
    assert "ai_session" in test_client.cookies
    return login.json()["user"]
