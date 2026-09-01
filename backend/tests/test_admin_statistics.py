"""Admin statistics: real KPIs, service_key isolation, no legacy users.plan."""
import itertools

from fastapi.testclient import TestClient

from conftest import register_and_login
from database import SessionLocal
import models
import main


_counter = itertools.count(1)


def _make_super(client):
    username = f"stats-admin-{next(_counter)}"
    register_and_login(client, username)
    db = SessionLocal()
    try:
        u = db.query(models.User).filter_by(username=username).one()
        u.is_admin = 1
        u.admin_role = "super_admin"
        db.commit()
    finally:
        db.close()
    return username


def test_dashboard_uses_real_kpis_and_no_legacy(client):
    _make_super(client)
    register_and_login(TestClient(main.app), f"stats-normal-{next(_counter)}")
    r = client.get("/admin/dashboard")
    assert r.status_code == 200, r.text
    body = r.json()
    ov = body["overview"]
    # new KPI keys present, legacy keys absent
    for k in ("total_users", "admin_users", "new_users_today", "paid_users", "effective_memberships", "today_ai_calls", "total_materials", "pending_tickets"):
        assert k in ov, k
    assert "total_courses" not in ov
    assert "active_users_today" not in ov
    assert "plan_counts" not in body
    # 30-day user growth
    assert len(body["user_growth"]) == 30


def test_statistics_endpoint_structure(client):
    _make_super(client)
    r = client.get("/admin/statistics")
    assert r.status_code == 200, r.text
    body = r.json()
    for k in ("users", "memberships", "materials", "tickets", "orders"):
        assert k in body, k
    assert "paid_users" in body["memberships"]
    assert "directions" in body["memberships"]
    assert set(body["memberships"]["directions"].keys()) == {"exam_11408", "course_learning", "programming"}
    assert "exam_11408" in body["materials"] and "legacy" in body["materials"]


def test_usage_summary_has_service_isolation(client):
    _make_super(client)
    r = client.get("/admin/usage-summary")
    assert r.status_code == 200, r.text
    ss = r.json()["service_stats"]
    assert set(ss.keys()) == {"exam_11408", "course_learning", "programming", "unknown"}
    assert "plan_counts" not in r.json()


def test_usage_trend_service_filter(client):
    _make_super(client)
    r = client.get("/admin/usage-trend?days=30&service_key=exam_11408")
    assert r.status_code == 200
    assert r.json()["service_key"] == "exam_11408"
    assert len(r.json()["items"]) == 30


def test_ai_logs_service_filter(client):
    _make_super(client)
    r = client.get("/admin/ai-logs?service_key=unknown&page_size=20")
    assert r.status_code == 200
    assert "total_pages" in r.json()
    for item in r.json()["items"]:
        assert not item["service_key"]  # unknown = null/empty service_key


def test_non_admin_rejected(client):
    tc = TestClient(main.app)
    register_and_login(tc, f"stats-user-{next(_counter)}")
    assert tc.get("/admin/dashboard").status_code == 403
    assert tc.get("/admin/statistics").status_code == 403
    assert tc.get("/admin/usage-summary").status_code == 403
    assert tc.get("/admin/usage-trend").status_code == 403
