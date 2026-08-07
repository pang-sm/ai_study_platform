from fastapi.testclient import TestClient

from conftest import register_and_login


def test_learning_report_save_list_detail_and_isolation(client: TestClient):
    register_and_login(client, "report-a")
    saved = client.post("/learning/reports/save", json={
        "username": "report-a",
        "course_id": "data_structure",
        "course_name": "数据结构",
        "report_type": "weekly",
        "title": "本周报告",
        "summary": "真实保存",
        "content": "本周完成了线性表练习。",
        "metrics": {"practice_sessions": 1},
        "suggestions": ["继续复习"],
    })
    assert saved.status_code == 200, saved.text
    report_id = saved.json()["report_id"]

    listed = client.get("/learning/reports", params={"username": "report-a"})
    assert listed.status_code == 200
    assert any(item["id"] == report_id for item in listed.json()["items"])
    detail = client.get(f"/learning/reports/{report_id}", params={"username": "report-a"})
    assert detail.status_code == 200
    assert detail.json()["content"] == "本周完成了线性表练习。"

    other = TestClient(client.app)
    try:
        register_and_login(other, "report-b")
        assert other.get("/learning/reports", params={"username": "report-a"}).status_code == 403
        assert other.get(f"/learning/reports/{report_id}", params={"username": "report-b"}).status_code == 404
        assert other.delete(f"/learning/reports/{report_id}", params={"username": "report-b"}).status_code == 404
    finally:
        other.close()
