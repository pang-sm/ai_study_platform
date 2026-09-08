from datetime import timedelta

from fastapi.testclient import TestClient

from conftest import register_and_login
import main
import models


def _first_leaf(nodes):
    for node in nodes:
        children = node.get("children") or []
        if children:
            leaf = _first_leaf(children)
            if leaf:
                return leaf
        else:
            return node
    return None


def _map_and_leaf(client: TestClient, username: str):
    response = client.get("/knowledge-map", params={"course_id": "data_structure", "username": username})
    assert response.status_code == 200, response.text
    payload = response.json()
    leaf = _first_leaf(payload["chapters"])
    assert leaf and leaf.get("code")
    return payload, leaf


def _leaf_status(payload, code: str):
    leaf = _first_leaf(payload["chapters"])
    if leaf and leaf["code"] == code:
        return leaf["status"]

    def find(nodes):
        for node in nodes:
            if node.get("code") == code:
                return node["status"]
            found = find(node.get("children") or [])
            if found:
                return found
        return None

    return find(payload["chapters"])


def test_knowledge_map_four_manual_statuses_persist_across_reload(client: TestClient):
    username = "knowledge-map-status"
    register_and_login(client, username)
    _, leaf = _map_and_leaf(client, username)

    for status in ("learning", "mastered", "review_due", "not_started"):
        saved = client.patch("/knowledge-map/progress", json={
            "username": username,
            "course_id": "data_structure",
            "knowledge_point_code": leaf["code"],
            "knowledge_point_title": leaf["title"],
            "status": status,
        })
        assert saved.status_code == 200, saved.text
        assert saved.json()["node"]["status"] == status
        assert saved.json()["node"]["stored_status"] == status
        assert saved.json()["node"]["user_confirmed_status"] == status

        reloaded, _ = _map_and_leaf(client, username)
        assert _leaf_status(reloaded, leaf["code"]) == status


def test_mastered_review_schedule_materializes_and_restarts(client: TestClient, monkeypatch):
    username = "knowledge-map-review-cycle"
    register_and_login(client, username)
    _, leaf = _map_and_leaf(client, username)
    started_at = main.utc_now()
    monkeypatch.setattr(main, "utc_now", lambda: started_at)
    mastered = client.patch("/knowledge-map/progress", json={
        "username": username, "course_id": "data_structure", "knowledge_point_code": leaf["code"],
        "knowledge_point_title": leaf["title"], "status": "mastered",
    })
    assert mastered.status_code == 200, mastered.text
    first_learned_at = mastered.json()["node"]["learned_at"]

    monkeypatch.setattr(main, "utc_now", lambda: started_at + timedelta(days=8))
    due_map, _ = _map_and_leaf(client, username)
    assert _leaf_status(due_map, leaf["code"]) == "review_due"

    restarted = client.patch("/knowledge-map/progress", json={
        "username": username,
        "course_id": "data_structure",
        "knowledge_point_code": leaf["code"],
        "knowledge_point_title": leaf["title"],
        "status": "mastered",
    })
    assert restarted.status_code == 200, restarted.text
    assert restarted.json()["node"]["status"] == "mastered"
    assert restarted.json()["node"]["learned_at"] != first_learned_at
    assert restarted.json()["node"]["review_due_at"]


def test_review_settings_recalculate_existing_learned_points(client: TestClient, monkeypatch):
    username = "knowledge-map-review-setting"
    register_and_login(client, username)
    _, leaf = _map_and_leaf(client, username)
    learned_at = main.utc_now()
    monkeypatch.setattr(main, "utc_now", lambda: learned_at)
    assert client.patch("/knowledge-map/progress", json={
        "username": username, "course_id": "data_structure", "knowledge_point_code": leaf["code"],
        "knowledge_point_title": leaf["title"], "status": "mastered",
    }).status_code == 200

    monkeypatch.setattr(main, "utc_now", lambda: learned_at + timedelta(days=2))
    saved = client.patch("/knowledge-map/review-settings", json={
        "username": username,
        "course_id": "data_structure",
        "review_interval_days": 1,
    })
    assert saved.status_code == 200, saved.text
    assert saved.json()["review_interval_days"] == 1
    reloaded_setting = client.get("/knowledge-map/review-settings", params={
        "username": username, "course_id": "data_structure"
    })
    assert reloaded_setting.json()["review_interval_days"] == 1
    reloaded_map, _ = _map_and_leaf(client, username)
    assert _leaf_status(reloaded_map, leaf["code"]) == "review_due"


def test_legacy_chinese_learned_value_is_read_as_mastered():
    legacy_progress = models.UserKnowledgeProgress(
        username="knowledge-map-legacy",
        course_id="data_structure",
        knowledge_point_id=0,
        status="\u5df2\u5b66\u4e60",
    )
    assert main._display_map_progress_status(legacy_progress) == "mastered"
    assert main.normalize_knowledge_status("\u672a\u5b66\u4e60") == "not_started"
    assert main.normalize_knowledge_status("\u5b66\u4e60\u4e2d") == "learning"
    assert main.normalize_knowledge_status("\u5df2\u5b66\u4e60") == "mastered"
    assert main.normalize_knowledge_status("\u5f85\u590d\u4e60") == "review_due"


def test_practice_suggestion_does_not_overwrite_confirmed_status(client: TestClient, db_session):
    username = "knowledge-map-practice"
    user_payload = register_and_login(client, username)
    _, leaf = _map_and_leaf(client, username)
    user = db_session.get(models.User, user_payload["id"])
    main._update_course_learning_progress(
        db_session,
        user=user,
        course_id="data_structure",
        point={"code": leaf["code"], "title": leaf["title"]},
        is_correct=True,
    )
    db_session.commit()
    saved = client.patch("/knowledge-map/progress", json={
        "username": username,
        "course_id": "data_structure",
        "knowledge_point_code": leaf["code"],
        "knowledge_point_title": leaf["title"],
        "status": "not_started",
    })
    assert saved.status_code == 200, saved.text

    main._update_course_learning_progress(
        db_session,
        user=user,
        course_id="data_structure",
        point={"code": leaf["code"], "title": leaf["title"]},
        is_correct=True,
    )
    db_session.commit()
    reloaded, _ = _map_and_leaf(client, username)
    assert _leaf_status(reloaded, leaf["code"]) == "not_started"
