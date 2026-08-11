import json

from fastapi.testclient import TestClient

from conftest import register_and_login
import main


def _fake_ai(_messages, timeout_seconds=60):
    return json.dumps({
        "stem": "线性表的顺序存储结构最适合哪种访问方式？",
        "options": {"A": "按下标随机访问", "B": "只允许尾部访问", "C": "不支持元素定位", "D": "只能反向访问"},
        "standard_answer": "A",
        "analysis": "顺序存储通过基址和下标可以直接计算元素位置。",
    }, ensure_ascii=False)


def test_course_ai_workbook_keeps_question_and_attempt_history(client: TestClient, monkeypatch):
    register_and_login(client, "workbook-owner")
    monkeypatch.setattr(main, "call_deepseek", _fake_ai)

    generated = client.post("/course-learning/practice/generate", json={
        "username": "workbook-owner",
        "course_id": "data_structure",
        "knowledge_point_title": "线性表",
        "chapter": "线性结构",
    })
    assert generated.status_code == 200, generated.text
    payload = generated.json()
    question_id = payload["question"]["id"]

    initial = client.get("/course-learning/practice/workbook", params={
        "username": "workbook-owner", "course_id": "data_structure",
    })
    assert initial.status_code == 200
    item = next(row for row in initial.json()["items"] if row["id"] == question_id)
    assert item["workbook_status"] == "unanswered"
    assert item["attempt_count"] == 1
    assert "standard_answer" not in item

    wrong = client.post(f"/course-learning/practice/{payload['attempt_id']}/submit", json={
        "username": "workbook-owner", "answer": "B",
    })
    assert wrong.status_code == 200, wrong.text
    assert wrong.json()["result"]["correct"] is False

    restarted = client.post(f"/course-learning/practice/workbook/{question_id}/attempts", json={
        "username": "workbook-owner",
    })
    assert restarted.status_code == 200, restarted.text
    assert restarted.json()["attempt_id"] != payload["attempt_id"]
    assert restarted.json()["question"]["id"] == question_id

    correct = client.post(f"/course-learning/practice/{restarted.json()['attempt_id']}/submit", json={
        "username": "workbook-owner", "answer": "A",
    })
    assert correct.status_code == 200, correct.text
    assert correct.json()["result"]["correct"] is True

    workbook = client.get("/course-learning/practice/workbook", params={
        "username": "workbook-owner", "course_id": "data_structure", "status": "correct",
    })
    assert workbook.status_code == 200
    item = next(row for row in workbook.json()["items"] if row["id"] == question_id)
    assert item["workbook_status"] == "correct"
    assert item["attempt_count"] == 2
    assert [attempt["correct"] for attempt in item["attempts"]] == [True, False]

    history = client.get("/course-learning/practice/history", params={
        "username": "workbook-owner", "course_id": "data_structure",
    })
    assert history.status_code == 200
    assert [row["question_id"] for row in history.json()["items"][:2]] == [question_id, question_id]
