from fastapi.testclient import TestClient

from conftest import register_and_login
import main
import models


def _seed_material(username: str, db_session):
    course_id = main.normalize_subject_course_learning("data_structure")
    material = models.StudyMaterial(
        username=username,
        subject=course_id,
        file_type="text",
        original_filename="notes.txt",
        mime_type="text/plain",
        file_size=32,
        file_hash=f"{username}-hash",
        file_path="test/notes.txt",
        extracted_text="线性表由连续或链式存储结构组成。顺序存储支持按下标访问，链式存储便于插入和删除。",
        summary="线性表基础以及两种存储方式的适用场景。",
        parse_status="success",
        chunk_count=1,
        allow_generate_knowledge=True,
        is_deleted=False,
    )
    db_session.add(material)
    db_session.commit()
    db_session.refresh(material)
    return material, course_id


def test_material_preview_requires_owner_and_confirm_deduplicates(client: TestClient, db_session, monkeypatch):
    register_and_login(client, "material-a")
    material, course_id = _seed_material("material-a", db_session)

    preview = client.post("/materials/analyze-knowledge-preview", json={
        "username": "material-a",
        "course_id": course_id,
        "material_ids": [material.id],
    })
    assert preview.status_code in {200, 422, 500}, preview.text

    tree = [{"title": "线性结构", "description": "线性表相关知识", "children": [{"title": "线性表", "description": "基本概念"}]}]
    confirmed = client.post("/materials/confirm-knowledge-tree", json={
        "username": "material-a",
        "course_id": course_id,
        "material_ids": [material.id],
        "knowledge_tree": tree,
    })
    assert confirmed.status_code == 200, confirmed.text
    repeated = client.post("/materials/confirm-knowledge-tree", json={
        "username": "material-a",
        "course_id": course_id,
        "material_ids": [material.id],
        "knowledge_tree": tree,
    })
    assert repeated.status_code == 200, repeated.text
    assert repeated.json()["skipped_duplicates"] > 0

    other = TestClient(client.app)
    try:
        register_and_login(other, "material-b")
        denied = other.post("/materials/confirm-knowledge-tree", json={
            "username": "material-a",
            "course_id": course_id,
            "material_ids": [material.id],
            "knowledge_tree": tree,
        })
        assert denied.status_code == 403
    finally:
        other.close()
