from datetime import timedelta

from fastapi.testclient import TestClient

from conftest import register_and_login
import main
import models


def _seed_scope_data(username, db_session):
    course_id = main.normalize_subject_course_learning("operating_system")
    other_course_id = main.normalize_subject_course_learning("data_structure")
    material = models.StudyMaterial(
        username=username,
        subject=course_id,
        file_type="text",
        original_filename="exam-scope-notes.txt",
        mime_type="text/plain",
        file_size=64,
        file_hash=f"{username}-scope-hash",
        file_path="test/exam-scope-notes.txt",
        extracted_text="进程管理和虚拟内存属于考试范围。",
        summary="考试范围资料摘要：进程管理和虚拟内存。",
        parse_status="success",
        source_type="exam_scope",
        is_deleted=False,
    )
    parent = models.KnowledgePoint(username=username, course_id=course_id, title="第三章", level=0, order_index=0)
    child_a = models.KnowledgePoint(username=username, course_id=course_id, title="进程管理", level=1, order_index=1)
    child_b = models.KnowledgePoint(username=username, course_id=course_id, title="虚拟内存", level=1, order_index=2)
    foreign_point = models.KnowledgePoint(username=username, course_id=other_course_id, title="线性表", level=0, order_index=0)
    db_session.add_all([material, parent, child_a, child_b, foreign_point])
    db_session.flush()
    child_a.parent_id = parent.id
    child_b.parent_id = parent.id
    material.updated_at = material.created_at + timedelta(days=1)
    db_session.commit()
    return course_id, other_course_id, material, parent, child_a, child_b, foreign_point


def test_exam_scope_endpoint_persists_sources_isolates_and_injects_ai_context(client: TestClient, db_session, monkeypatch):
    register_and_login(client, "exam-scope-user-a")
    course_id, other_course_id, material, parent, child_a, child_b, foreign_point = _seed_scope_data("exam-scope-user-a", db_session)

    uploaded = client.post("/materials/upload", data={
        "username": "exam-scope-user-a",
        "subject": course_id,
        "source_type": "exam_scope",
    }, files={"file": ("uploaded-exam-scope.txt", b"final exam scope", "text/plain")})
    assert uploaded.status_code == 200, uploaded.text
    uploaded_id = uploaded.json()["material_id"]
    assert uploaded.json()["material"]["source_type"] == "exam_scope"
    auto_linked = client.get(f"/course-learning/exam-scope?course_id={course_id}")
    assert uploaded_id in auto_linked.json()["scope"]["material_ids"]

    manual = client.put("/course-learning/exam-scope", json={"course_id": course_id, "manual_text": "只考第三章，不考文件系统"})
    assert manual.status_code == 200, manual.text
    linked = client.put("/course-learning/exam-scope", json={"course_id": course_id, "material_ids": [material.id]})
    assert linked.status_code == 200, linked.text
    selected = client.put("/course-learning/exam-scope", json={"course_id": course_id, "knowledge_point_ids": [parent.id]})
    assert selected.status_code == 200, selected.text
    scope = selected.json()["scope"]
    assert scope["manual_text"] == "只考第三章，不考文件系统"
    assert scope["material_ids"] == [material.id]
    assert scope["knowledge_point_ids"] == [child_a.id, child_b.id]
    assert scope["materials"][0]["source_type"] == "exam_scope"
    assert scope["materials"][0]["created_at"] != scope["materials"][0]["updated_at"]

    changed_manual = client.put("/course-learning/exam-scope", json={"course_id": course_id, "manual_text": "只考进程管理和虚拟内存"})
    changed_scope = changed_manual.json()["scope"]
    assert changed_scope["material_ids"] == [material.id]
    assert changed_scope["knowledge_point_ids"] == [child_a.id, child_b.id]

    legacy_settings = client.post("/course-learning/exam-settings", json={
        "username": "exam-scope-user-a", "course_id": course_id, "exam_date": "2026-08-20", "target": "80", "daily_review": "60",
    })
    assert legacy_settings.status_code == 200, legacy_settings.text
    reloaded = client.get(f"/course-learning/exam-scope?course_id={course_id}")
    assert reloaded.status_code == 200, reloaded.text
    assert reloaded.json()["scope"]["material_ids"] == [material.id]
    assert reloaded.json()["scope"]["knowledge_point_ids"] == [child_a.id, child_b.id]

    foreign_course = client.put("/course-learning/exam-scope", json={"course_id": course_id, "knowledge_point_ids": [foreign_point.id]})
    assert foreign_course.status_code == 400
    invalid_point = client.put("/course-learning/exam-scope", json={"course_id": course_id, "knowledge_point_ids": [999999]})
    assert invalid_point.status_code == 400
    invalid_material = client.put("/course-learning/exam-scope", json={"course_id": course_id, "material_ids": [999999]})
    assert invalid_material.status_code == 400
    other_course = client.get(f"/course-learning/exam-scope?course_id={other_course_id}")
    assert other_course.status_code == 200
    assert other_course.json()["scope"]["manual_text"] == ""

    captured = []
    def fail_after_capture(messages):
        captured.extend(messages)
        raise RuntimeError("test AI fallback")
    monkeypatch.setattr(main, "call_deepseek", fail_after_capture)
    generated = client.post("/learning/plans/generate-preview", json={
        "username": "exam-scope-user-a", "course_id": course_id, "plan_scene": "exam", "plan_type": "exam", "days": 3,
    })
    assert generated.status_code == 200, generated.text
    assert generated.json()["exam_scope_context"]["material_ids"] == [material.id]
    assert "只考进程管理和虚拟内存" in captured[-1]["content"]
    assert "进程管理" in captured[-1]["content"]

    other = TestClient(client.app)
    try:
        register_and_login(other, "exam-scope-user-b")
        denied_identity = other.put("/course-learning/exam-scope", json={"username": "exam-scope-user-a", "course_id": course_id, "manual_text": "越权"})
        assert denied_identity.status_code == 403
        isolated = other.get(f"/course-learning/exam-scope?course_id={course_id}")
        assert isolated.status_code == 200
        assert isolated.json()["scope"]["manual_text"] == ""
    finally:
        other.close()
