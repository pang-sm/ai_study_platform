import json

from fastapi.testclient import TestClient

from conftest import register_and_login
import main


def _fake_ai(_messages, timeout_seconds=60):
    return json.dumps({
        "stem": "哪个选项最适合描述当前知识点？",
        "options": {"A": "理解概念", "B": "只背标题", "C": "跳过练习", "D": "忽略条件"},
        "standard_answer": "A",
        "analysis": "先理解概念，再通过练习验证边界条件。",
    }, ensure_ascii=False)


def test_course_practice_generate_submit_history_and_user_isolation(client: TestClient, monkeypatch):
    register_and_login(client, "practice-a")
    monkeypatch.setattr(main, "call_deepseek", _fake_ai)

    generated = client.post("/course-learning/practice/generate", json={
        "username": "practice-a",
        "course_id": "data_structure",
        "knowledge_point_title": "线性表",
        "chapter": "线性结构",
    })
    assert generated.status_code == 200, generated.text
    payload = generated.json()
    assert payload["generation_mode"] == "ai"
    assert "standard_answer" not in payload["question"]
    attempt_id = payload["attempt_id"]

    other = TestClient(client.app)
    try:
        register_and_login(other, "practice-b")
        assert other.get("/course-learning/practice/history", params={"username": "practice-a"}).status_code == 403
        assert other.post(f"/course-learning/practice/{attempt_id}/submit", json={"username": "practice-b", "answer": "A"}).status_code in {403, 404}
    finally:
        other.close()

    submitted = client.post(f"/course-learning/practice/{attempt_id}/submit", json={"username": "practice-a", "answer": "A"})
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["result"]["correct"] is True
    history = client.get("/course-learning/practice/history", params={"username": "practice-a", "course_id": "data_structure"})
    assert history.status_code == 200
    assert any(item["id"] == attempt_id for item in history.json()["items"])
