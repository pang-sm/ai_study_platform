from fastapi.testclient import TestClient

from conftest import register_and_login
from database import SessionLocal
import models


def _active_tracks(username: str):
    db = SessionLocal()
    try:
        return {
            track.track_type: (bool(track.is_active), track.onboarding_detail_json or "")
            for track in db.query(models.UserLearningTrack)
            .join(models.User, models.User.id == models.UserLearningTrack.user_id)
            .filter(models.User.username == username)
            .all()
        }
    finally:
        db.close()


def test_partial_new_direction_onboarding_preserves_current_direction(client: TestClient):
    username = "onboarding-return-owner"
    register_and_login(client, username)

    completed_course = client.post(
        "/me/onboarding",
        params={"username": username},
        json={
            "nickname": "验收用户",
            "learning_direction": "university_course",
            "learning_goal_type": "university_course",
            "onboarding_completed": True,
            "preferred_subjects": ["数据结构"],
        },
    )
    assert completed_course.status_code == 200, completed_course.text

    partial_programming = client.post(
        "/programming/onboarding",
        json={
            "main_language": "Python",
            "level": "零基础",
            "problems": ["概念不熟"],
            "onboarding_completed": False,
        },
    )
    assert partial_programming.status_code == 200, partial_programming.text
    tracks = _active_tracks(username)
    assert tracks["university_course"][0] is True
    assert tracks["programming"][0] is False

    partial_course = client.post(
        "/course-learning/onboarding",
        json={
            "major": "计算机科学与技术",
            "grade": "大一",
            "selected_courses": ["数据结构"],
            "material_types": [],
            "onboarding_completed": False,
        },
    )
    assert partial_course.status_code == 200, partial_course.text
    tracks_after = _active_tracks(username)
    assert tracks_after["university_course"][0] is True
    assert tracks_after["programming"][0] is False
