import json

from fastapi.testclient import TestClient

from conftest import register_and_login
import models


def _new_client(app, username: str) -> TestClient:
    client = TestClient(app)
    register_and_login(client, username)
    return client


def test_private_attempt_and_import_job_resources_are_user_scoped(client: TestClient, db_session):
    owner = register_and_login(client, "resource-owner")
    ai_attempt = models.AIQuestionAttempt(
        username=owner["username"],
        subject_key="data_structure",
        subject_name="Data Structure",
        question_ids_json="[]",
        status="in_progress",
        total_questions=0,
    )
    chapter_attempt = models.ExamPracticeAttempt(
        username=owner["username"],
        subject_key="data_structure",
        practice_type="chapter",
        source_type="chapter",
        question_ids_json="[]",
        status="in_progress",
        total_questions=0,
    )
    import_job = models.PracticeImportJob(
        username=owner["username"],
        course_id="data_structure",
        status="pending",
        progress_message="queued",
    )
    db_session.add_all([ai_attempt, chapter_attempt, import_job])
    db_session.commit()
    db_session.refresh(ai_attempt)
    db_session.refresh(chapter_attempt)
    db_session.refresh(import_job)

    other = _new_client(client.app, "resource-other")
    try:
        # A forged identity is rejected before the resource lookup.
        assert other.post(
            f"/exam/11408/data_structure/ai-questions/attempts/{ai_attempt.id}/answers",
            json={"username": "resource-owner", "answers": {}},
        ).status_code == 403
        assert other.post(
            f"/exam/11408/data_structure/chapter-practice/attempts/{chapter_attempt.id}/answers",
            json={"username": "resource-owner", "answers": {}},
        ).status_code == 403

        # Omitting the legacy username still cannot cross the ownership filter.
        assert other.post(
            f"/exam/11408/data_structure/ai-questions/attempts/{ai_attempt.id}/answers",
            json={"answers": {}},
        ).status_code == 404
        assert other.post(
            f"/exam/11408/data_structure/chapter-practice/attempts/{chapter_attempt.id}/answers",
            json={"answers": {}},
        ).status_code == 404
        assert other.get(f"/practice/import-paper/jobs/{import_job.id}").status_code == 404
    finally:
        other.close()


def test_username_spoofing_is_rejected_for_private_updates(client: TestClient):
    register_and_login(client, "identity-owner")
    other = _new_client(client.app, "identity-other")
    try:
        for method, path, body in (
            ("put", "/exam-408/target-school", {"username": "identity-owner", "school": "北京大学"}),
            ("put", "/exam-408/motto", {"username": "identity-owner", "motto": "forged"}),
            ("put", "/me/tracks/exam_408/package", {"username": "identity-owner", "package_type": "basic"}),
            ("post", "/learning/plans/generate-preview", {"username": "identity-owner", "course_id": "data_structure"}),
        ):
            response = getattr(other, method)(path, json=body)
            assert response.status_code == 403, (method, path, response.status_code, response.text)
    finally:
        other.close()


def test_code_diagnostics_requires_authentication(client: TestClient):
    response = client.post("/code/diagnose", json={"language": "python", "code": "print(1)"})
    assert response.status_code == 401


def test_interactive_websocket_uses_server_identity(client: TestClient):
    register_and_login(client, "ws-owner")
    other = _new_client(client.app, "ws-other")
    try:
        with other.websocket_connect("/code/interactive-run") as websocket:
            websocket.send_text(json.dumps({
                "username": "ws-owner",
                "language": "python",
                "code": "print(1)",
            }))
            message = json.loads(websocket.receive_text())
            assert message["type"] == "error"
            assert "当前登录用户" in message["message"]

        unauthenticated = TestClient(client.app)
        try:
            with unauthenticated.websocket_connect("/code/interactive-run") as websocket:
                websocket.send_text(json.dumps({"language": "python", "code": "print(1)"}))
                message = json.loads(websocket.receive_text())
                assert message["type"] == "error"
        finally:
            unauthenticated.close()
    finally:
        other.close()
