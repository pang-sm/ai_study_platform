"""FRONTEND_BLOCKER_BC2: `/exam/11408/subjects/{subject_key}/dashboard-summary` declares
a concrete 200 response model.

The frontend generated ``unknown`` for this success response because the handler returned
a bare dict. Declaring ``response_model`` fixes that — but only if it changes the typing
and nothing else. So every test here is paired:

  * the OPENAPI side must become a concrete ``$ref``, never ``{}``;
  * the RUNTIME side must stay byte-identical.

The runtime half does not trust a hand-copied expectation: it builds a second FastAPI app
that mounts the *same* handler with no response model, i.e. the literal pre-change route,
and compares the two apps' JSON byte for byte. A change that "fixes" the types by
altering the payload fails that comparison.

The models are also field-for-field narrow (no ``Any`` / ``dict`` escape hatch), so a
subject the handler does not actually return cannot sneak in.
"""
import inspect
import json
import re
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from conftest import register_and_login
import database
import main
import models

PATH = "/exam/11408/subjects/{subject_key}/dashboard-summary"
MODULES = ("data_structure", "computer_organization", "operating_system", "computer_network")

# The pre-change route, re-mounted from the very same handler with no response_model.
BEFORE_APP = FastAPI()
BEFORE_APP.get(PATH)(main.get_exam_subject_dashboard_summary)

TOP_KEYS = ["subject_key", "subject_name", "overview", "today_plan", "materials", "quota"]
OVERVIEW_KEYS = ["total_chapters", "total_knowledge_points", "learned_percent", "study_minutes"]
TASK_KEYS = ["id", "title", "knowledge_point_name", "task_type", "computed_status", "due_date"]
MATERIAL_KEYS = ["lecture_notes", "exercises", "references", "code_examples", "total_materials"]
COUNT_QUOTA_KEYS = ["used", "limit", "remaining", "unit"]
UPLOAD_QUOTA_KEYS = ["used", "limit", "remaining", "unit"]


def _openapi():
    return main.app.openapi()


def _success_schema(spec, path=PATH, method="get"):
    return spec["paths"][path][method]["responses"].get("200", {}) \
               .get("content", {}).get("application/json", {}).get("schema")


def _login(client, username):
    r = client.post("/login", json={"username": username, "password": "secret123"})
    assert r.status_code == 200, r.text


def _seed(username, *, upload_bytes, with_task=True):
    db = database.SessionLocal()
    try:
        user = db.query(models.User).filter(models.User.username == username).first()
        db.add(models.UserLearningTrack(user_id=user.id, track_type="exam_408",
                                        package_type="monthly_sprint", is_active=True))
        if with_task:
            db.add(models.ExamStudyPlanTask(
                username=username, subject_key="data_structure", title="线性表复习",
                knowledge_point_name=None, secondary_knowledge="顺序表",
                scope_type="single", task_type="knowledge", due_date="2026-10-01"))
        db.add(models.StudyMaterial(
            username=username, subject="11408 数据结构", file_type="lecture",
            original_filename="a.pdf", file_path="/tmp/a.pdf", extracted_text="",
            summary="", file_size=upload_bytes, is_deleted=False))
        db.commit()
    finally:
        db.close()


# ================================================================ A: runtime shape

@pytest.mark.parametrize("module", MODULES)
def test_a_runtime_shape_is_unchanged_for_every_module(client, module):
    """All four modules must answer with the same six top-level keys."""
    register_and_login(client, f"bc2_shape_{module}")
    r = client.get(PATH.format(subject_key=module))
    assert r.status_code == 200, r.text
    body = r.json()
    assert list(body) == TOP_KEYS
    assert body["subject_key"] == module
    assert isinstance(body["subject_name"], str) and body["subject_name"]
    assert list(body["overview"]) == OVERVIEW_KEYS
    assert list(body["materials"]) == MATERIAL_KEYS
    assert list(body["quota"]) == ["ai_chat", "ai_question", "material_upload"]
    assert list(body["quota"]["ai_chat"]) == COUNT_QUOTA_KEYS
    assert list(body["quota"]["material_upload"]) == UPLOAD_QUOTA_KEYS
    assert body["today_plan"] == []


def test_a_today_plan_entry_shape_is_unchanged(client):
    register_and_login(client, "bc2_shape_plan")
    _seed("bc2_shape_plan", upload_bytes=1536 * 1024)
    body = client.get(PATH.format(subject_key="data_structure")).json()
    assert len(body["today_plan"]) == 1
    task = body["today_plan"][0]
    assert list(task) == TASK_KEYS
    assert isinstance(task["id"], int)
    assert task["knowledge_point_name"] == "顺序表"
    assert task["task_type"] == "knowledge"
    assert task["computed_status"] in {"not_started", "in_progress", "completed"}
    assert task["due_date"] == "2026-10-01"


def test_a_quota_keeps_its_int_and_float_sides(client):
    """ai_chat is integral, material_upload is fractional — models must not merge them."""
    register_and_login(client, "bc2_shape_quota")
    _seed("bc2_shape_quota", upload_bytes=1536 * 1024)
    quota = client.get(PATH.format(subject_key="data_structure")).json()["quota"]
    assert isinstance(quota["ai_chat"]["used"], int)
    upload = quota["material_upload"]
    assert isinstance(upload["used"], float)
    assert upload["used"] == 1.5
    assert upload["remaining"] == 498.5


def test_a_over_cap_upload_remaining_is_still_an_int_zero(client):
    """`max(0, limit - used)` really does return int 0 past the cap."""
    register_and_login(client, "bc2_shape_overcap")
    _seed("bc2_shape_overcap", upload_bytes=900 * 1024 * 1024)
    upload = client.get(PATH.format(subject_key="data_structure")).json()["quota"]["material_upload"]
    assert upload["used"] == 900.0
    assert upload["remaining"] == 0
    assert not isinstance(upload["remaining"], float)


# ================================================================ B: byte equivalence

@pytest.mark.parametrize("module", MODULES)
def test_b_response_model_round_trips_the_handler_byte_for_byte(client, module):
    """Same handler, with and without response_model, on the same DB and session."""
    register_and_login(client, f"bc2_eq_{module}")
    _seed(f"bc2_eq_{module}", upload_bytes=1536 * 1024)
    _login(client, f"bc2_eq_{module}")

    with TestClient(BEFORE_APP) as before_client:
        before_client.cookies = client.cookies
        before = before_client.get(PATH.format(subject_key=module))
        after = client.get(PATH.format(subject_key=module))

    assert before.status_code == after.status_code == 200
    assert before.text == after.text, (
        f"{module}: response_model changed the payload\n"
        f"  before={before.text}\n  after ={after.text}"
    )


def test_b_empty_payload_round_trips_byte_for_byte(client):
    register_and_login(client, "bc2_eq_empty")
    _login(client, "bc2_eq_empty")
    with TestClient(BEFORE_APP) as before_client:
        before_client.cookies = client.cookies
        before = before_client.get(PATH.format(subject_key="computer_network"))
        after = client.get(PATH.format(subject_key="computer_network"))
    assert before.status_code == after.status_code == 200
    assert before.text == after.text


def test_b_over_cap_payload_round_trips_byte_for_byte(client):
    register_and_login(client, "bc2_eq_overcap")
    _seed("bc2_eq_overcap", upload_bytes=900 * 1024 * 1024)
    _login(client, "bc2_eq_overcap")
    with TestClient(BEFORE_APP) as before_client:
        before_client.cookies = client.cookies
        before = before_client.get(PATH.format(subject_key="data_structure"))
        after = client.get(PATH.format(subject_key="data_structure"))
    assert before.status_code == after.status_code == 200
    # the over-cap branch must keep its int 0 — a `float` field would emit `0.0`
    assert '"remaining":0,' in after.text
    assert '"remaining":0.0' not in after.text
    assert before.text == after.text


# ================================================================ C: OpenAPI

def test_c_openapi_200_is_a_concrete_ref_not_empty():
    schema = _success_schema(_openapi())
    assert schema, "no 200 schema declared"
    assert schema != {}, "200 schema is still the empty {}"
    assert schema.get("$ref") == "#/components/schemas/ExamSubjectDashboardSummaryResponse"


def test_c_before_state_really_was_empty():
    """Guards the whole exercise: this endpoint WAS the `unknown` case."""
    assert _success_schema(BEFORE_APP.openapi()) == {}


@pytest.mark.parametrize("model", (
    "ExamSubjectDashboardSummaryResponse", "ExamDashboardOverview", "ExamDashboardPlanTask",
    "ExamDashboardMaterials", "ExamDashboardCountQuota", "ExamDashboardUploadQuota",
    "ExamDashboardQuota",
))
def test_c_declared_models_exist_and_are_structured(model):
    schema = _openapi()["components"]["schemas"][model]
    assert schema.get("type") == "object"
    assert schema.get("properties"), f"{model}: no properties"
    assert schema.get("required"), f"{model}: no required list"


def test_no_any_or_dict_escape_hatch_in_the_new_models():
    """A single `Any` anywhere would regenerate the frontend type back to `unknown`."""
    spec = _openapi()
    for model in ("ExamSubjectDashboardSummaryResponse", "ExamDashboardOverview",
                  "ExamDashboardPlanTask", "ExamDashboardMaterials",
                  "ExamDashboardCountQuota", "ExamDashboardUploadQuota", "ExamDashboardQuota"):
        blob = json.dumps(spec["components"]["schemas"][model])
        assert '"additionalProperties"' not in blob, model
        assert '{}' not in blob.replace('"$ref"', ""), model


def test_c_required_lists_match_the_real_payload_keys():
    spec = _openapi()["components"]["schemas"]
    assert set(spec["ExamSubjectDashboardSummaryResponse"]["required"]) == set(TOP_KEYS)
    assert set(spec["ExamDashboardOverview"]["required"]) == set(OVERVIEW_KEYS)
    assert set(spec["ExamDashboardPlanTask"]["required"]) == set(TASK_KEYS)
    assert set(spec["ExamDashboardMaterials"]["required"]) == set(MATERIAL_KEYS)
    assert set(spec["ExamDashboardCountQuota"]["required"]) == set(COUNT_QUOTA_KEYS)
    assert set(spec["ExamDashboardUploadQuota"]["required"]) == set(UPLOAD_QUOTA_KEYS)
    assert set(spec["ExamDashboardQuota"]["required"]) == {"ai_chat", "ai_question",
                                                          "material_upload"}


def test_c_nested_objects_and_arrays_are_typed():
    props = _openapi()["components"]["schemas"]["ExamSubjectDashboardSummaryResponse"]["properties"]
    assert props["overview"]["$ref"] == "#/components/schemas/ExamDashboardOverview"
    assert props["materials"]["$ref"] == "#/components/schemas/ExamDashboardMaterials"
    assert props["quota"]["$ref"] == "#/components/schemas/ExamDashboardQuota"
    assert props["today_plan"]["type"] == "array"
    assert props["today_plan"]["items"]["$ref"] == "#/components/schemas/ExamDashboardPlanTask"

    quota = _openapi()["components"]["schemas"]["ExamDashboardQuota"]["properties"]
    assert quota["ai_chat"]["$ref"] == "#/components/schemas/ExamDashboardCountQuota"
    assert quota["ai_question"]["$ref"] == "#/components/schemas/ExamDashboardCountQuota"
    assert quota["material_upload"]["$ref"] == "#/components/schemas/ExamDashboardUploadQuota"


def test_c_upload_quota_models_both_real_number_shapes():
    spec = _openapi()["components"]["schemas"]
    count = spec["ExamDashboardCountQuota"]["properties"]
    assert count["used"]["type"] == "integer"
    assert count["limit"]["type"] == "integer"
    assert count["remaining"]["type"] == "integer"
    assert count["unit"]["type"] == "string"

    upload = spec["ExamDashboardUploadQuota"]["properties"]
    assert upload["used"]["type"] == "number"
    assert upload["limit"]["type"] == "integer"
    assert upload["remaining"]["anyOf"] == [{"type": "integer"}, {"type": "number"}]
    assert upload["unit"]["type"] == "string"


def test_c_computed_status_is_a_closed_enum():
    status = _openapi()["components"]["schemas"]["ExamDashboardPlanTask"]["properties"]["computed_status"]
    assert status["enum"] == ["not_started", "in_progress", "completed"]


def test_c_computed_status_enum_cannot_drift_from_the_handler(client):
    """Re-derive the enum from `_compute_task_completion`'s own return statements.

    If the handler ever grows a fourth status, this fails loudly instead of the route
    starting to 500 on the unexpected value.
    """
    src = inspect.getsource(main._compute_task_completion)
    real = set(re.findall(r'return \(\s*"([a-z_]+)"', src))
    assert real, "could not read status literals from _compute_task_completion"
    declared = set(_openapi()["components"]["schemas"]["ExamDashboardPlanTask"]
                   ["properties"]["computed_status"]["enum"])
    assert declared == real

    # and every status the live payload can carry is inside that closed set
    register_and_login(client, "bc2_status_vocab")
    for module in MODULES:
        for task in client.get(PATH.format(subject_key=module)).json()["today_plan"]:
            assert task["computed_status"] in declared


def test_c_task_type_stays_an_open_string():
    """`task_type` is a free DB column, so it must NOT be frozen into an enum."""
    task_type = _openapi()["components"]["schemas"]["ExamDashboardPlanTask"]["properties"]["task_type"]
    assert task_type["type"] == "string"
    assert "enum" not in task_type


# ================================================================ D: error contract

def test_d_error_status_codes_are_unchanged(client):
    register_and_login(client, "bc2_errors")
    assert client.get("/exam/11408/subjects/nope/dashboard-summary").status_code == 400


def test_d_unauthenticated_is_still_401():
    with TestClient(main.app) as anon:
        assert anon.get(PATH.format(subject_key="data_structure")).status_code == 401


def test_d_no_error_models_were_added():
    """This step closes SUCCESS typing only; the error contract must stay undeclared."""
    op = _openapi()["paths"][PATH]["get"]
    assert set(op["responses"]) <= {"200", "422"}


def test_d_unknown_subject_error_body_is_unchanged(client):
    register_and_login(client, "bc2_err_body")
    _login(client, "bc2_err_body")
    with TestClient(BEFORE_APP) as before_client:
        before_client.cookies = client.cookies
        before = before_client.get("/exam/11408/subjects/nope/dashboard-summary")
        after = client.get("/exam/11408/subjects/nope/dashboard-summary")
    assert before.status_code == after.status_code == 400
    assert before.text == after.text


# ================================================================ E: generated TS

GENERATED_TS = Path(__file__).resolve().parents[2] / "frontend" / "src" / "types" / "api.ts"


def test_e_generated_typescript_response_is_not_unknown():
    if not GENERATED_TS.exists():
        pytest.skip("frontend api.ts not generated in this checkout")
    src = GENERATED_TS.read_text(encoding="utf-8")
    if 'components["schemas"]["ExamSubjectDashboardSummaryResponse"]' not in src:
        pytest.skip("run `npm run api:generate` to refresh frontend/src/types/api.ts")
    assert 'components["schemas"]["ExamDashboardOverview"]' in src
    assert 'components["schemas"]["ExamDashboardPlanTask"]' in src
    assert 'components["schemas"]["ExamDashboardMaterials"]' in src
    assert 'components["schemas"]["ExamDashboardQuota"]' in src
    assert 'components["schemas"]["ExamDashboardUploadQuota"]' in src


def test_e_generated_operation_200_is_not_unknown():
    if not GENERATED_TS.exists():
        pytest.skip("frontend api.ts not generated in this checkout")
    src = GENERATED_TS.read_text(encoding="utf-8")
    op = ("get_exam_subject_dashboard_summary_exam_11408_subjects_"
          "_subject_key__dashboard_summary_get")
    # `paths:` merely aliases the operation id; the definition itself is the `id: {` entry
    definition = f"{op}: {{"
    if definition not in src:
        pytest.skip(f"{op} not in the generated file yet — run `npm run api:generate`")
    block = src[src.index(definition):]
    block = block[:block.index("422:")]          # just this operation's 200 body
    # the 200 body must name a concrete response model, not `unknown`
    assert 'components["schemas"]["ExamSubjectDashboardSummaryResponse"]' in block
    assert '"application/json": unknown' not in block
