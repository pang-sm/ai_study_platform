"""Who may reach a stored material file, and what the library says about it.

The course library is one VIEW of the learner's own material library, and both read the same
rows. A file is delivered by ONE pair of endpoints (`/materials/{id}/preview` and
`/materials/{id}/download`) whichever door it came through, and this file pins that shared
contract from the outside: owner access, another learner's refusal, a deleted file's refusal,
and the two response headers a browser needs — inline for a preview, attachment with a UTF-8
filename for a download.
"""
from __future__ import annotations

import uuid
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient
from conftest import register_and_login

import main

COURSE = "数据结构"
COURSE_MATERIALS = "/course-learning/courses/{course}/materials"


@pytest.fixture
def owner(client):
    """A learner with one selected course, through the REAL onboarding route."""
    username = f"matlib-{uuid.uuid4().hex[:8]}"
    register_and_login(client, username)
    response = client.post("/course-learning/onboarding", json={
        "major": "计算机科学与技术", "grade": "大二", "semester": "上学期",
        "selected_courses": [COURSE], "material_types": ["课件"],
        "onboarding_completed": True,
    })
    assert response.status_code == 200, response.text
    return client, username


def _upload_course(client: TestClient, filename: str, body: bytes) -> int:
    response = client.post(
        COURSE_MATERIALS.format(course=COURSE),
        files={"file": (filename, body, "text/plain")},
    )
    assert response.status_code == 200, response.text
    return response.json()["material_id"]


def _upload_personal(client: TestClient, filename: str, body: bytes) -> int:
    response = client.post("/personal-materials/upload", files={"file": (filename, body, "text/plain")})
    assert response.status_code == 200, response.text
    return response.json()["id"]


# ---------------------------------------------------------------- owner access

def test_owner_reads_back_both_their_own_files(owner):
    """A course upload and a personal upload are delivered by the same endpoints, byte for byte."""
    client, _ = owner
    course_id = _upload_course(client, "课程讲义.txt", b"COURSE_MATERIAL_BODY")
    personal_id = _upload_personal(client, "个人笔记.txt", b"PERSONAL_MATERIAL_BODY")

    for material_id, body in ((course_id, b"COURSE_MATERIAL_BODY"), (personal_id, b"PERSONAL_MATERIAL_BODY")):
        download = client.get(f"/materials/{material_id}/download")
        assert download.status_code == 200, download.text
        assert download.content == body

        preview = client.get(f"/materials/{material_id}/preview")
        assert preview.status_code == 200, preview.text
        assert preview.content == body


def test_download_is_an_attachment_named_as_the_learner_named_it(owner):
    """The browser must save the learner's own filename, not the id the file is stored under."""
    client, _ = owner
    filename = "数据结构 讲义 01.txt"
    material_id = _upload_personal(client, filename, b"BODY")

    download = client.get(f"/materials/{material_id}/download")
    assert download.status_code == 200, download.text
    assert download.headers["content-type"].startswith("text/plain")

    disposition = download.headers["content-disposition"]
    assert disposition.startswith("attachment;")
    assert "filename*=UTF-8''" in disposition
    # The non-ASCII name has to travel percent-encoded in the RFC 5987 parameter.
    assert quote(filename) in disposition


def test_preview_is_inline_not_an_attachment(owner):
    """An inline disposition is what makes the browser render the file instead of saving it."""
    client, _ = owner
    material_id = _upload_personal(client, "预览.txt", b"PREVIEW_BODY")

    preview = client.get(f"/materials/{material_id}/preview")
    assert preview.status_code == 200, preview.text
    assert preview.headers["content-disposition"].startswith("inline;")
    assert preview.headers["content-type"].startswith("text/plain")


# ---------------------------------------------------------------- other learners

def test_another_learner_reaches_neither_library(owner, db_session):
    client, _ = owner
    course_id = _upload_course(client, "private-course.txt", b"COURSE_PRIVATE_BODY")
    personal_id = _upload_personal(client, "private-personal.txt", b"PERSONAL_PRIVATE_BODY")

    with TestClient(main.app) as other:
        register_and_login(other, f"matlib-other-{uuid.uuid4().hex[:8]}")

        for material_id in (course_id, personal_id):
            for route in ("download", "preview"):
                response = other.get(f"/materials/{material_id}/{route}")
                assert response.status_code in {401, 403, 404}, response.text
                # A refusal must not disclose that the file exists, let alone what it is called.
                assert "private-course.txt" not in response.text
                assert "private-personal.txt" not in response.text

        # And the other learner's own library simply does not hold them.
        listed = other.get("/library/materials").json()["materials"]
        assert all(item["id"] != personal_id for item in listed)


# ---------------------------------------------------------------- deleted files

def test_a_deleted_file_can_be_neither_viewed_nor_downloaded(owner):
    client, _ = owner
    course_id = _upload_course(client, "gone-course.txt", b"GONE_COURSE")
    personal_id = _upload_personal(client, "gone-personal.txt", b"GONE_PERSONAL")

    assert client.delete(f"/materials/{course_id}").status_code == 200
    assert client.delete(f"/personal-materials/{personal_id}").status_code == 200

    for material_id in (course_id, personal_id):
        for route in ("download", "preview"):
            assert client.get(f"/materials/{material_id}/{route}").status_code == 404
    assert all(item["id"] != personal_id for item in client.get("/library/materials").json()["materials"])


# ---------------------------------------------------------------- the library payload

def test_the_library_payload_carries_what_a_picker_shows(owner):
    """Name, type, size, upload time, parse state, origin — and the server's own preview decision.

    The picker renders exactly this and nothing more: it may not re-derive which file types
    open in a browser, and it may never be handed a storage path, chunk text or internal
    parse plumbing.
    """
    client, _ = owner
    response = client.post(
        "/personal-materials/upload",
        files={"file": ("完整 笔记.md", "# 标题".encode(), "text/markdown")},
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["filename"] == "完整 笔记.md"
    assert payload["file_type"] == "text"
    assert payload["parse_status"] == "success"
    assert payload["size"] > 0
    assert payload["created_at"]
    assert payload["can_preview"] is True
    assert payload["preview_url"] == f"/materials/{payload['id']}/preview"
    assert payload["can_download"] is True
    assert payload["download_url"] == f"/materials/{payload['id']}/download"
    assert payload["scope_type"] == "personal"
    assert payload["source_label"] == "个人资料"

    for forbidden in ("file_path", "storage_path", "chunk_count", "extracted_text"):
        assert forbidden not in payload

    # The list answers the same shape, so the picker and the upload agree about the file.
    listed = client.get("/library/materials").json()["materials"]
    row = next(item for item in listed if item["id"] == payload["id"])
    assert row["preview_url"] == payload["preview_url"]
    assert row["can_preview"] is True and row["can_download"] is True
