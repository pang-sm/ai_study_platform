from fastapi.testclient import TestClient

from conftest import register_and_login
from database import SessionLocal
import models
import json


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


def test_exam_track_completion_flag_distinguishes_legacy_payloads(client: TestClient):
    username = "exam-direction-status-owner"
    register_and_login(client, username)

    completed_course = client.post(
        "/me/onboarding",
        params={"username": username},
        json={
            "nickname": "验收用户",
            "learning_direction": "university_course",
            "learning_goal_type": "university_course",
            "onboarding_completed": True,
        },
    )
    assert completed_course.status_code == 200, completed_course.text

    db = SessionLocal()
    try:
        user = db.query(models.User).filter(models.User.username == username).one()
        user_id = user.id
        incomplete = models.UserLearningTrack(
            user_id=user_id,
            track_type="exam_408",
            plan="free",
            onboarding_detail_json=json.dumps({"learning_goal_type": "exam_408"}),
            is_active=False,
        )
        db.add(incomplete)
        db.commit()
    finally:
        db.close()

    incomplete_profile = client.post("/me", json={"username": username})
    assert incomplete_profile.status_code == 200, incomplete_profile.text
    incomplete_track = next(track for track in incomplete_profile.json()["user"]["tracks"] if track["track_type"] == "exam_408")
    assert incomplete_track["onboarding_detail"].get("exam_408_onboarding_completed") is None

    db = SessionLocal()
    try:
        track = db.query(models.UserLearningTrack).filter(
            models.UserLearningTrack.user_id == user_id,
            models.UserLearningTrack.track_type == "exam_408",
        ).one()
        track.onboarding_detail_json = json.dumps({
            "learning_goal_type": "exam_408",
            "exam_time": "2027 年 12 月",
            "stage": "基础阶段",
        }, ensure_ascii=False)
        db.commit()
    finally:
        db.close()

    completed_profile = client.post("/me", json={"username": username})
    assert completed_profile.status_code == 200, completed_profile.text
    completed_track = next(track for track in completed_profile.json()["user"]["tracks"] if track["track_type"] == "exam_408")
    assert completed_track["onboarding_detail"]["exam_408_onboarding_completed"] is True
