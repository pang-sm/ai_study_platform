from fastapi.testclient import TestClient

from conftest import register_and_login
from database import SessionLocal
import models


def _complete_direction(client: TestClient, service_key: str):
    if service_key == "course_learning":
        response = client.post("/course-learning/onboarding", json={
            "major": "计算机科学与技术",
            "grade": "大一",
            "semester": "上学期",
            "selected_courses": ["数据结构"],
            "onboarding_completed": True,
        })
    elif service_key == "programming":
        response = client.post("/programming/onboarding", json={
            "main_language": "Python",
            "level": "零基础",
            "onboarding_completed": True,
        })
    else:
        response = client.post("/me/onboarding", json={
            "learning_direction": "11408 备考",
            "learning_goal_type": "exam_408",
            "onboarding_completed": True,
            "preferred_subjects": ["数据结构"],
        })
    assert response.status_code == 200, response.text


def _guide(client: TestClient, service_key: str):
    response = client.get("/me/guides")
    assert response.status_code == 200, response.text
    return response.json()["guides"][service_key]


def test_first_time_guide_defaults_and_completion_are_service_isolated(client: TestClient):
    register_and_login(client, "guide-owner")
    initial = client.get("/me/guides")
    assert initial.status_code == 200
    assert set(initial.json()["guides"]) == {"course_learning", "exam_11408", "programming"}
    assert all(not item["completed"] for item in initial.json()["guides"].values())

    _complete_direction(client, "course_learning")
    assert _guide(client, "course_learning")["eligible"] is True
    complete = client.post("/me/guides/course_learning/complete")
    assert complete.status_code == 200, complete.text
    assert complete.json()["guide"]["completed"] is True
    assert complete.json()["guide"]["skipped"] is False
    assert _guide(client, "programming")["completed"] is False
    assert _guide(client, "exam_11408")["completed"] is False

    duplicate = client.post("/me/guides/course_learning/complete", json={"skipped": True})
    assert duplicate.status_code == 200
    assert duplicate.json()["guide"]["completed"] is True
    assert duplicate.json()["guide"]["skipped"] is False


def test_each_direction_can_complete_and_skip_without_changing_track_or_membership(client: TestClient, db_session):
    user = register_and_login(client, "guide-track-owner")
    for service_key in ("course_learning", "exam_11408", "programming"):
        _complete_direction(client, service_key)
        before = client.post("/me", json={}).json()["user"]
        saved = client.post(f"/me/guides/{service_key}/complete", json={"skipped": service_key == "exam_11408"})
        assert saved.status_code == 200, saved.text
        assert saved.json()["guide"]["completed"] is True
        assert saved.json()["guide"]["skipped"] is (service_key == "exam_11408")
        after = client.post("/me", json={}).json()["user"]
        assert after["active_track_type"] == before["active_track_type"]
        assert after["service_plans"] == before["service_plans"]

    db_user = db_session.query(models.User).filter(models.User.id == user["id"]).one()
    tracks = {track.track_type: track for track in db_user.tracks} if hasattr(db_user, "tracks") else {}
    assert not tracks or all(track.onboarding_detail_json for track in tracks.values())


def test_first_time_guides_are_current_user_scoped_and_reject_invalid_or_ineligible(client: TestClient):
    register_and_login(client, "guide-a")
    other = TestClient(client.app)
    try:
        register_and_login(other, "guide-b")
        _complete_direction(client, "programming")
        completed = client.post("/me/guides/programming/complete")
        assert completed.status_code == 200
        assert _guide(other, "programming")["completed"] is False

        assert client.post("/me/guides/not-real/complete").status_code == 404
        assert other.post("/me/guides/programming/complete").status_code == 403
    finally:
        other.close()
