"""FRONTEND_BLOCKER_BC1: the canonical Exam Prep endpoints declare real response models.

The blocked frontend generated ``unknown`` for these success responses because the FastAPI
handlers returned bare dicts. Declaring ``response_model`` fixes the typing — but ONLY if
it changes the typing and nothing else. So every test here is paired:

  * the OPENAPI side must become concrete ($ref / typed schema, never `{}` or `unknown`);
  * the RUNTIME side must stay byte-identical.

A change that fixes the types by altering the payload would pass the first half and fail
the second, which is the failure this file exists to catch.
"""
import json
from pathlib import Path

import pytest

from conftest import register_and_login
import main

# The complete canonical Exam Prep surface (derived from routers/exam_prep.py, not guessed).
CANONICAL_ENDPOINTS = (
    ("GET", "/exam/prep/profile", "ExamPrepProfileResponse"),
    ("PUT", "/exam/prep/profile", "ExamPrepProfileResponse"),
    ("GET", "/exam/prep/catalog", "ExamPrepCatalogResponse"),
    ("GET", "/exam/prep/catalog/tracks", "ExamCatalogTracksResponse"),
    ("GET", "/exam/prep/catalog/subjects", "ExamCatalogSubjectsResponse"),
    ("GET", "/exam/prep/subjects/{subject_id}/content-status", "ExamContentStatusResponse"),
)

PROFILE_KEYS = ["configured", "exam_type", "selected_track", "selected_subjects",
                "target_exam_year", "subjects"]
SUBJECT_KEYS = ["id", "display_name", "category", "availability", "has_questions",
                "has_past_papers", "has_knowledge_tree", "description",
                "suggested_tracks", "modules"]
TRACK_KEYS = ["id", "display_name", "exam_type", "availability", "has_content",
              "description", "subject_options", "suggested_subjects"]
MODULE_KEYS = ["id", "display_name"]
CONTENT_STATUS_KEYS = ["subject_id", "availability", "has_questions", "has_past_papers",
                       "has_knowledge_tree", "modules"]


def _openapi():
    return main.app.openapi()


def _success_schema(spec, method, path):
    op = spec["paths"][path][method.lower()]
    return op["responses"].get("200", {}).get("content", {}) \
             .get("application/json", {}).get("schema")


# ================================================================ A–D: runtime shape

def test_a_get_profile_runtime_shape_is_unchanged(client):
    register_and_login(client, "bc1_shape_get")
    body = client.get("/exam/prep/profile").json()
    assert list(body) == PROFILE_KEYS
    assert body["configured"] is False
    assert body["exam_type"] == "postgraduate"
    assert body["selected_track"] is None
    assert body["selected_subjects"] == []
    assert body["target_exam_year"] is None
    assert body["subjects"] == []


def test_b_put_profile_runtime_shape_is_unchanged(client):
    register_and_login(client, "bc1_shape_put")
    r = client.put("/exam/prep/profile", json={
        "selected_track": "cs_408", "selected_subjects": ["cs_408", "math_1"],
        "target_exam_year": 2027})
    assert r.status_code == 200, r.text
    body = r.json()
    assert list(body) == PROFILE_KEYS
    assert body["configured"] is True
    assert body["selected_track"] == "cs_408"
    assert body["selected_subjects"] == ["cs_408", "math_1"]
    assert body["target_exam_year"] == 2027
    assert [s["id"] for s in body["subjects"]] == ["cs_408", "math_1"]
    # a framework-only subject is still fully described in its own payload
    assert list(body["subjects"][0]) == SUBJECT_KEYS
    assert list(body["subjects"][1]) == SUBJECT_KEYS
    assert body["subjects"][1]["availability"] == "framework_only"


def test_c_catalog_runtime_shape_is_unchanged(client):
    body = client.get("/exam/prep/catalog").json()
    assert list(body) == ["catalog_version", "exam_type", "tracks", "subjects",
                          "active_subject_ids", "framework_only_subject_ids"]
    assert list(body["tracks"][0]) == TRACK_KEYS
    assert list(body["subjects"][0]) == SUBJECT_KEYS
    assert list(body["subjects"][0]["modules"][0]) == MODULE_KEYS
    assert body["active_subject_ids"] == ["cs_408"]

    tracks = client.get("/exam/prep/catalog/tracks").json()
    assert list(tracks) == ["catalog_version", "tracks"]
    assert list(tracks["tracks"][0]) == TRACK_KEYS

    subjects = client.get("/exam/prep/catalog/subjects").json()
    assert list(subjects) == ["catalog_version", "subjects"]
    assert list(subjects["subjects"][0]) == SUBJECT_KEYS


def test_d_content_status_runtime_shape_is_unchanged(client):
    body = client.get("/exam/prep/subjects/cs_408/content-status").json()
    assert list(body) == CONTENT_STATUS_KEYS
    assert body["subject_id"] == "cs_408"
    assert body["availability"] == "active"
    assert [m["id"] for m in body["modules"]] == [
        "data_structure", "computer_organization", "operating_system", "computer_network"]


def test_profile_subject_object_is_never_narrowed(client):
    """The union with the degraded 2-key form must not collapse a full subject.

    ``UnknownExamSubject`` uses ``extra="forbid"`` precisely so a full catalog payload can
    never round-trip through the narrow model.
    """
    register_and_login(client, "bc1_union")
    body = client.put("/exam/prep/profile", json={
        "selected_track": "cs_408", "selected_subjects": ["cs_408"]}).json()
    assert len(body["subjects"][0]) == len(SUBJECT_KEYS)


# ================================================================ E/G/H: OpenAPI

@pytest.mark.parametrize("method,path,model", CANONICAL_ENDPOINTS)
def test_e_openapi_success_schema_is_concrete(method, path, model):
    schema = _success_schema(_openapi(), method, path)
    assert schema, f"{method} {path}: no 200 schema declared"
    assert schema != {}, f"{method} {path}: empty schema"
    assert schema.get("$ref") == f"#/components/schemas/{model}", schema


@pytest.mark.parametrize("method,path,model", CANONICAL_ENDPOINTS)
def test_e_declared_model_exists_and_is_structured(method, path, model):
    spec = _openapi()
    assert model in spec["components"]["schemas"], f"{model} missing from components"
    schema = spec["components"]["schemas"][model]
    assert schema.get("type") == "object"
    assert schema.get("properties"), f"{model}: no properties"
    assert schema.get("required"), f"{model}: no required list"


def test_e_profile_model_marks_nullable_fields_and_nested_arrays():
    spec = _openapi()
    profile = spec["components"]["schemas"]["ExamPrepProfileResponse"]
    props, required = profile["properties"], set(profile["required"])

    assert required == set(PROFILE_KEYS), "every field is always present in the payload"

    # nullable, but present — the payload always carries the key
    for field in ("selected_track", "target_exam_year"):
        assert {o.get("type") for o in props[field]["anyOf"]} == {"string", "null"} \
            or {o.get("type") for o in props[field]["anyOf"]} == {"integer", "null"}

    assert props["selected_subjects"]["type"] == "array"
    assert props["selected_subjects"]["items"] == {"type": "string"}
    assert props["subjects"]["type"] == "array"
    refs = [o.get("$ref") for o in props["subjects"]["items"]["anyOf"]]
    assert refs == ["#/components/schemas/ExamSubjectSummary",
                    "#/components/schemas/UnknownExamSubject"]


def test_e_availability_is_a_closed_enum():
    spec = _openapi()
    for model in ("ExamSubjectSummary", "ExamTrackSummary", "ExamContentStatusResponse"):
        avail = spec["components"]["schemas"][model]["properties"]["availability"]
        assert avail["enum"] == ["active", "framework_only"], model


def test_e_subject_capability_flags_are_booleans_and_modules_are_typed():
    spec = _openapi()
    props = spec["components"]["schemas"]["ExamSubjectSummary"]["properties"]
    for flag in ("has_questions", "has_past_papers", "has_knowledge_tree"):
        assert props[flag]["type"] == "boolean", flag
    assert props["modules"]["items"] == {"$ref": "#/components/schemas/ExamModuleSummary"}
    assert props["suggested_tracks"]["items"] == {"type": "string"}
    module = spec["components"]["schemas"]["ExamModuleSummary"]
    assert set(module["required"]) == {"id", "display_name"}


def test_e_catalog_model_lists_are_typed():
    spec = _openapi()
    props = spec["components"]["schemas"]["ExamPrepCatalogResponse"]["properties"]
    assert props["tracks"]["items"] == {"$ref": "#/components/schemas/ExamTrackSummary"}
    assert props["subjects"]["items"] == {"$ref": "#/components/schemas/ExamSubjectSummary"}
    assert props["active_subject_ids"]["items"] == {"type": "string"}
    assert props["framework_only_subject_ids"]["items"] == {"type": "string"}


def test_h_cs408_active_content_status_is_typed_and_matches_runtime(client):
    body = client.get("/exam/prep/subjects/cs_408/content-status").json()
    model = _openapi()["components"]["schemas"]["ExamContentStatusResponse"]
    assert set(body) == set(model["required"])
    assert body["availability"] in model["properties"]["availability"]["enum"]


def test_g_framework_only_subject_keeps_its_409_and_is_not_typed_as_success(client):
    """A framework-only subject must still REFUSE — not return a typed empty success."""
    r = client.get("/exam/prep/subjects/math_1/content-status")
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "EXAM_CONTENT_NOT_AVAILABLE"
    # and the 200 schema is not what answered
    assert _success_schema(_openapi(), "GET",
                           "/exam/prep/subjects/{subject_id}/content-status") is not None


# ================================================================ I: error contract

def test_i_error_status_codes_are_unchanged(client):
    register_and_login(client, "bc1_errors")
    # unknown subject -> 404 (it does not exist)
    assert client.get("/exam/prep/subjects/nope/content-status").status_code == 404
    # framework-only -> 409 (it exists and is selectable, it just has no content)
    assert client.get("/exam/prep/subjects/math_1/content-status").status_code == 409
    # invalid profile input -> 400
    assert client.put("/exam/prep/profile",
                      json={"selected_track": "nope"}).status_code == 400
    assert client.put("/exam/prep/profile", json={
        "selected_track": "cs_408", "selected_subjects": ["ghost"]}).status_code == 400
    assert client.put("/exam/prep/profile", json={
        "selected_track": "cs_408", "target_exam_year": 1800}).status_code == 400


def test_i_unauthenticated_profile_is_still_401(client):
    from fastapi.testclient import TestClient
    with TestClient(main.app) as anon:
        assert anon.get("/exam/prep/profile").status_code == 401


def test_no_error_models_were_added_to_these_endpoints():
    """This step closes SUCCESS typing only; the error contract must stay undeclared."""
    spec = _openapi()
    for method, path, _ in CANONICAL_ENDPOINTS:
        op = spec["paths"][path][method.lower()]
        declared = set(op["responses"])
        assert declared <= {"200", "422"}, f"{method} {path}: {declared}"


# ================================================================ F: generated TS

GENERATED_TS = Path(__file__).resolve().parents[2] / "frontend" / "src" / "types" / "api.ts"


@pytest.mark.parametrize("method,path,model", CANONICAL_ENDPOINTS)
def test_f_generated_typescript_response_is_not_unknown(method, path, model):
    """The actual blocker: the generated client must not type these 200s as `unknown`."""
    if not GENERATED_TS.exists():
        pytest.skip("frontend api.ts not generated in this checkout")
    src = GENERATED_TS.read_text(encoding="utf-8")
    if f'components["schemas"]["{model}"]' not in src:
        pytest.skip(f"{model} not in the generated file yet — run `npm run api:generate`")
    assert f"operations" in src
    # the operation must reference the declared model somewhere in its 200 body
    assert model in src, f"{model} absent from generated types"
