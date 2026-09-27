"""The 408 subject's own material library.

`/exam/11408/subjects/{subject_key}/materials` is the exam side of the ONE material
pipeline, so what these tests check is the SCOPE, not the parser: that a subject's material
is stored under the id the rest of the exam space already derives, that it is listed back
only under that subject, and that nothing about the surface invents a second way to store or
read a file.

The domain rules it leans on are pre-existing and are asserted here rather than assumed:
`<module>_11408` classifies as `exam_11408` in `main._material_domain`, which is what gives
it a quota of its own and the label "11408" in the library.
"""
import pytest
from fastapi.testclient import TestClient

from conftest import register_and_login
from learning.spaces.exam_prep import materials as exam_materials
from learning.spaces.exam_prep.catalog import CS408_MODULE_DISPLAY
from learning.spaces.exam_prep.scope import ExamScopeError

import main

MODULES = ("data_structure", "computer_organization", "operating_system", "computer_network")


def test_the_scope_is_the_id_the_rest_of_the_exam_space_already_stores():
    for module in MODULES:
        scoped = exam_materials.subject_material_scope(module)
        assert scoped["course_id"] == f"{module}_11408"
        assert scoped["subject_key"] == module
        assert scoped["subject"] == f"11408 {CS408_MODULE_DISPLAY[module]}"
        assert scoped["track"] == "exam_11408"
        # The quota and the library label are read off that same id, so the scope this module
        # builds is the domain the pipeline will classify it as — not a new one.
        assert main._material_domain(scoped["course_id"], scoped["subject_key"]) == "exam_11408"


def test_a_module_408_does_not_have_is_refused_rather_than_filed():
    for unknown in ("linear_algebra", "", "data_structure_11408", None):
        with pytest.raises(ExamScopeError):
            exam_materials.subject_material_scope(unknown)  # type: ignore[arg-type]


def test_a_408_material_is_named_in_the_library_it_appears_in():
    # The learner's library lists every file they own, so a 408 upload surfaces there too.
    # It has to be named there rather than shown as its stored key.
    names = exam_materials.subject_material_names()
    assert names == {f"{module}_11408": f"11408 {CS408_MODULE_DISPLAY[module]}" for module in MODULES}


def test_uploading_into_a_subject_lists_it_back_only_under_that_subject(client: TestClient):
    register_and_login(client, "exam-materials-scope")

    uploaded = client.post(
        "/exam/11408/subjects/data_structure/materials",
        files={"file": ("structure-notes.txt", b"linear list notes", "text/plain")},
    )
    assert uploaded.status_code == 200, uploaded.text
    assert uploaded.json()["subject_key"] == "data_structure"
    assert uploaded.json()["course_id"] == "data_structure_11408"

    listed = client.get("/exam/11408/subjects/data_structure/materials")
    assert listed.status_code == 200
    payload = listed.json()
    assert payload["subject_key"] == "data_structure"
    assert payload["course_id"] == "data_structure_11408"
    assert payload["total"] == 1
    item = payload["items"][0]
    assert item["original_filename"] == "structure-notes.txt"
    assert item["course_id"] == "data_structure_11408"
    assert item["subject_key"] == "data_structure"

    # The scope is the SUBJECT, not the learner: another paper's library does not inherit it.
    other = client.get("/exam/11408/subjects/operating_system/materials").json()
    assert other["total"] == 0
    assert other["items"] == []


def test_an_empty_subject_library_is_a_real_empty_list(client: TestClient):
    register_and_login(client, "exam-materials-empty")
    payload = client.get("/exam/11408/subjects/computer_network/materials").json()
    assert payload == {"subject_key": "computer_network",
                       "course_id": "computer_network_11408", "items": [], "total": 0}


def test_a_subject_outside_408_is_refused_on_both_verbs(client: TestClient):
    register_and_login(client, "exam-materials-bad-subject")

    listed = client.get("/exam/11408/subjects/linear_algebra/materials")
    assert listed.status_code == 400
    assert listed.json()["detail"] == "Unknown subject: linear_algebra"

    uploaded = client.post(
        "/exam/11408/subjects/linear_algebra/materials",
        files={"file": ("x.txt", b"x", "text/plain")},
    )
    assert uploaded.status_code == 400
    assert uploaded.json()["detail"] == "Unknown subject: linear_algebra"


def test_another_learners_material_is_not_in_this_learners_subject(client: TestClient):
    register_and_login(client, "exam-materials-owner")
    assert client.post(
        "/exam/11408/subjects/computer_organization/materials",
        files={"file": ("coa.txt", b"cpu pipeline", "text/plain")},
    ).status_code == 200

    client.cookies.clear()
    register_and_login(client, "exam-materials-other")
    assert client.get("/exam/11408/subjects/computer_organization/materials").json()["total"] == 0


def test_the_material_delete_is_the_one_library_delete_that_already_exists(client: TestClient):
    """Deleting is not reimplemented for the exam space: the row is the same row, so the
    library's own soft delete removes it from this subject's list too."""
    register_and_login(client, "exam-materials-delete")
    uploaded = client.post(
        "/exam/11408/subjects/computer_network/materials",
        files={"file": ("net.txt", b"tcp handshake", "text/plain")},
    )
    assert uploaded.status_code == 200, uploaded.text
    material_id = uploaded.json()["material_id"]

    assert client.get("/exam/11408/subjects/computer_network/materials").json()["total"] == 1
    deleted = client.delete(f"/library/materials/{material_id}")
    assert deleted.status_code == 200, deleted.text
    assert client.get("/exam/11408/subjects/computer_network/materials").json()["total"] == 0
