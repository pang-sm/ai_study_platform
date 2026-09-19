"""FRONTEND_BLOCKER_BC3: the CS408 knowledge / study-plan endpoints declare real 200 models.

They generated ``unknown`` for the frontend because both handlers returned bare dicts.
Declaring ``response_model`` fixes the typing — but ONLY if it changes the typing and
nothing else. So every test here is paired:

  * the OPENAPI side must become a concrete ``$ref``, never ``{}``;
  * the RUNTIME side must stay equivalent.

The runtime half does not trust a hand-copied expectation: it builds a second FastAPI app
mounting the *same* handlers with no response model — the literal pre-change routes — and
compares the two apps' payloads. The hard gate is CANONICAL equality (order-independent,
type-exact). Byte order is compared separately and is documented, because the four seed
maps disagree among themselves about where ``chapter_no`` sits inside a chapter, so no
single field order can reproduce both module groups.

GET /exam/11408/subjects/{subject_key}/study-plan
PATCH /exam/11408/subjects/{subject_key}/study-plan/knowledge-items/{item_code}
"""
import inspect
import json
import re
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from conftest import register_and_login
import database
import main
import models

GET_PATH = "/exam/11408/subjects/{subject_key}/study-plan"
PATCH_PATH = "/exam/11408/subjects/{subject_key}/study-plan/knowledge-items/{item_code}"
MODULES = ("data_structure", "computer_organization", "operating_system", "computer_network")

GET_MODEL = "ExamStudyPlanResponse"
PATCH_MODEL = "ExamKnowledgeItemUpdateResponse"

TOP_KEYS = ["course_id", "course_name", "subject_key", "subject_name",
            "settings", "stats", "review_interval_days", "chapters", "tasks"]
SETTINGS_KEYS = ["learning_goal", "start_date", "daily_hours", "weekly_days",
                 "review_strategy", "show_completed"]
STATS_KEYS = ["total_knowledge_points", "mastered", "total_sections", "sections_completed",
              "sections_learning", "sections_not_started", "overall_progress",
              "overall_status"]
TASK_KEYS = ["id", "username", "subject_key", "subject_name", "title",
             "knowledge_point_name", "scope_type", "task_type", "computed_status",
             "completion_reason", "action_target", "due_date", "note", "created_at",
             "updated_at", "status", "primary_knowledge", "secondary_knowledge"]
PROGRESS_KEYS = ["id", "course_id", "knowledge_point_code", "knowledge_point_title",
                 "status", "stored_status", "user_confirmed_status",
                 "system_suggested_status", "ai_recommended_status", "ai_assessment",
                 "learned_at", "review_due_at", "review_interval_days", "updated_at"]
CHAPTER_KEYS = ["code", "title", "children", "chapter_no", "id", "is_leaf", "status",
                "stored_status", "user_confirmed_status", "system_suggested_status",
                "ai_recommended_status", "ai_assessment", "status_counts",
                "chapter_completion_rate", "chapter_status", "section_count",
                "sections_completed"]
SECTION_KEYS = ["code", "title", "children", "id", "is_leaf", "status", "stored_status",
                "user_confirmed_status", "system_suggested_status",
                "ai_recommended_status", "ai_assessment", "status_counts", "leaf_stats",
                "chapter_practice_completed", "section_status", "completion_rate"]
NODE_KEYS = ["code", "title", "children", "id", "is_leaf", "status", "stored_status",
             "user_confirmed_status", "system_suggested_status", "ai_recommended_status",
             "ai_assessment", "status_counts"]
PATCH_KEYS = ["success", "knowledge_point_code", "knowledge_point_title", "status",
              "stored_status"]

STATUSES = ["not_started", "learning", "mastered", "review_due"]

# The pre-change routes: same handlers, no response_model.
BEFORE_APP = FastAPI()
BEFORE_APP.get(GET_PATH)(main.get_exam_subject_study_plan)
BEFORE_APP.patch(PATCH_PATH)(main.update_exam_study_plan_knowledge_item)

SEED_DIR = Path(main.__file__).resolve().parent / "seed_data" / "knowledge_maps"


# ---------------------------------------------------------------- helpers

def _openapi():
    return main.app.openapi()


def _success_schema(spec, path, method):
    return spec["paths"][path][method]["responses"].get("200", {}) \
               .get("content", {}).get("application/json", {}).get("schema")


def _components(spec):
    return spec["components"]["schemas"]


def canonical(text):
    """Order-independent but TYPE-EXACT: 0 and 0.0 stay distinguishable."""
    return json.dumps(json.loads(text), sort_keys=True, ensure_ascii=False)


def grant_exam_plan(username, plan="monthly_sprint"):
    """Entitlement for `learning_plan` — free resolves to 403, so the route needs a plan."""
    db = database.SessionLocal()
    try:
        user = db.query(models.User).filter(models.User.username == username).first()
        db.add(models.UserServiceMembership(user_id=user.id, service_key="exam_11408",
                                            is_enabled=True, plan=plan, status="active"))
        db.commit()
    finally:
        db.close()


def entitled_client(client, username):
    register_and_login(client, username)
    grant_exam_plan(username)
    assert client.post("/login", json={"username": username,
                                       "password": "secret123"}).status_code == 200
    return username


def seed_leaves(module="data_structure"):
    raw = json.loads((SEED_DIR / f"{module}_11408.json").read_text(encoding="utf-8"))
    idx = main._build_enriched_map_index(raw["chapters"])
    leaves = [k for k, v in idx.items() if main._is_leaf_node(v)]
    sections = [k for k, v in idx.items() if not main._is_leaf_node(v)]
    return leaves, sections


def add_progress(username, code, status, *, due=None, **cols):
    db = database.SessionLocal()
    try:
        now = main.utc_now()
        db.add(models.UserKnowledgeProgress(
            username=username, course_id="data_structure_11408", knowledge_point_id=0,
            knowledge_point_code=code, knowledge_point_title=f"t-{status}",
            status=status, learned_at=now if status not in (None, "not_started") else None,
            review_due_at=due, review_interval_days=7, updated_at=now, **cols))
        db.commit()
    finally:
        db.close()


def patch_payload(subject_key, item_code, status, **extra):
    body = {"username": None, "subject_key": subject_key,
            "course_id": f"{subject_key}_11408", "knowledge_point_code": item_code,
            "status": status}
    body.update(extra)
    return body


def tree(nodes, depth=0):
    """Yield (depth, node) for every node in the study-plan tree."""
    for node in nodes:
        yield depth, node
        yield from tree(node.get("children") or [], depth + 1)


# ================================================================ A/B: OpenAPI

def test_a_get_study_plan_success_schema_is_concrete():
    schema = _success_schema(_openapi(), GET_PATH, "get")
    assert schema, "GET study-plan: no 200 schema declared"
    assert schema != {}, "GET study-plan: 200 schema is still the empty {}"
    assert schema.get("$ref") == f"#/components/schemas/{GET_MODEL}"


def test_b_patch_knowledge_success_schema_is_concrete():
    schema = _success_schema(_openapi(), PATCH_PATH, "patch")
    assert schema, "PATCH knowledge-items: no 200 schema declared"
    assert schema != {}, "PATCH knowledge-items: 200 schema is still the empty {}"
    assert schema.get("$ref") == f"#/components/schemas/{PATCH_MODEL}"


def test_a_b_before_state_really_was_empty():
    """Guards the whole exercise: both endpoints WERE the `unknown` case."""
    assert _success_schema(BEFORE_APP.openapi(), GET_PATH, "get") == {}
    assert _success_schema(BEFORE_APP.openapi(), PATCH_PATH, "patch") == {}


@pytest.mark.parametrize("model", (
    GET_MODEL, PATCH_MODEL, "ExamStudyPlanSettings", "ExamStudyPlanStats",
    "ExamStudyPlanTaskItem", "ExamStudyPlanChapter", "ExamStudyPlanSection",
    "ExamStudyPlanKnowledgeNode", "ExamKnowledgeProgressDetail",
    "ExamKnowledgeStatusCounts", "ExamStudyPlanLeafStats",
))
def test_ab_declared_models_exist_and_are_structured(model):
    schema = _components(_openapi())[model]
    assert schema.get("type") == "object"
    assert schema.get("properties"), f"{model}: no properties"
    assert schema.get("required"), f"{model}: no required list"


def test_ab_no_any_or_dict_escape_hatch():
    """Any `Any` / free-form object would regenerate as `unknown` and re-block F1C1.

    `additionalProperties: false` (from the tree models' `extra="forbid"`) is the
    opposite of an escape hatch, so it is allowed; `true` or a schema is not.
    """
    specs = _components(_openapi())
    for model in (GET_MODEL, PATCH_MODEL, "ExamStudyPlanSettings", "ExamStudyPlanStats",
                  "ExamStudyPlanTaskItem", "ExamStudyPlanChapter", "ExamStudyPlanSection",
                  "ExamStudyPlanKnowledgeNode", "ExamKnowledgeProgressDetail",
                  "ExamKnowledgeStatusCounts", "ExamStudyPlanLeafStats"):
        schema = specs[model]
        assert schema.get("additionalProperties") in (None, False), model
        assert "{}" not in json.dumps(schema).replace('"$ref"', ""), model


def test_ab_required_lists_match_the_real_payload_keys():
    specs = _components(_openapi())
    assert set(specs[GET_MODEL]["required"]) == set(TOP_KEYS)
    assert set(specs["ExamStudyPlanSettings"]["required"]) == set(SETTINGS_KEYS)
    assert set(specs["ExamStudyPlanStats"]["required"]) == set(STATS_KEYS)
    assert set(specs["ExamStudyPlanTaskItem"]["required"]) == set(TASK_KEYS)
    assert set(specs["ExamKnowledgeProgressDetail"]["required"]) == set(PROGRESS_KEYS)
    assert set(specs["ExamKnowledgeStatusCounts"]["required"]) == set(STATUSES)
    assert set(specs["ExamStudyPlanLeafStats"]["required"]) == {
        "total", "mastered", "learning", "not_started", "review_due"}
    # `optional` and the progress block are genuinely conditional -> NOT required
    assert set(specs["ExamStudyPlanKnowledgeNode"]["required"]) == set(NODE_KEYS)
    assert set(specs["ExamStudyPlanSection"]["required"]) == set(SECTION_KEYS)
    assert set(specs["ExamStudyPlanChapter"]["required"]) == set(CHAPTER_KEYS)
    assert "optional" not in specs["ExamStudyPlanKnowledgeNode"]["required"]
    assert "progress" not in specs["ExamStudyPlanKnowledgeNode"]["required"]


def test_ab_hierarchy_is_typed_recursively():
    specs = _components(_openapi())
    assert specs[GET_MODEL]["properties"]["chapters"]["items"]["$ref"] == \
        "#/components/schemas/ExamStudyPlanChapter"
    assert specs[GET_MODEL]["properties"]["tasks"]["items"]["$ref"] == \
        "#/components/schemas/ExamStudyPlanTaskItem"
    assert specs["ExamStudyPlanChapter"]["properties"]["children"]["items"]["$ref"] == \
        "#/components/schemas/ExamStudyPlanSection"
    assert specs["ExamStudyPlanSection"]["properties"]["children"]["items"]["$ref"] == \
        "#/components/schemas/ExamStudyPlanKnowledgeNode"
    # the node model references ITSELF — arbitrary seed depth stays typeable
    assert specs["ExamStudyPlanKnowledgeNode"]["properties"]["children"]["items"]["$ref"] == \
        "#/components/schemas/ExamStudyPlanKnowledgeNode"
    assert specs["ExamStudyPlanSection"]["properties"]["leaf_stats"]["$ref"] == \
        "#/components/schemas/ExamStudyPlanLeafStats"
    assert specs["ExamStudyPlanKnowledgeNode"]["properties"]["status_counts"]["$ref"] == \
        "#/components/schemas/ExamKnowledgeStatusCounts"


def test_ab_status_enum_is_closed():
    specs = _components(_openapi())
    for model, field in (("ExamStudyPlanKnowledgeNode", "status"),
                         ("ExamStudyPlanSection", "status"),
                         ("ExamStudyPlanChapter", "status"),
                         ("ExamKnowledgeProgressDetail", "status"),
                         (PATCH_MODEL, "status")):
        assert specs[model]["properties"][field]["enum"] == STATUSES, f"{model}.{field}"
    for model in ("ExamStudyPlanSection", "ExamStudyPlanChapter"):
        assert specs[model]["properties"]["section_status" if model.endswith("Section")
                                          else "chapter_status"]["enum"] == \
            ["not_started", "learning", "completed"], model
    assert specs["ExamStudyPlanStats"]["properties"]["overall_status"]["enum"] == \
        ["not_started", "learning", "completed"]
    assert specs["ExamStudyPlanTaskItem"]["properties"]["computed_status"]["enum"] == \
        ["not_started", "in_progress", "completed"]
    assert specs["ExamStudyPlanTaskItem"]["properties"]["action_target"]["enum"] == \
        ["knowledge_map", "practice_center"]


def test_ab_legacy_status_columns_stay_open_strings():
    """`stored_status` / `user_confirmed_status` pass raw legacy values through, so they
    must NOT be narrowed to the display enum (a legacy Chinese value is preserved)."""
    specs = _components(_openapi())
    node = specs["ExamStudyPlanKnowledgeNode"]["properties"]
    for field in ("stored_status", "user_confirmed_status", "system_suggested_status",
                  "ai_recommended_status", "ai_assessment"):
        assert "enum" not in node[field], field
    prog = specs["ExamKnowledgeProgressDetail"]["properties"]
    for field in ("stored_status", "user_confirmed_status", "system_suggested_status",
                  "ai_recommended_status", "ai_assessment"):
        assert "enum" not in prog[field], field


def test_ab_status_enum_cannot_drift_from_the_handler():
    """Re-derive the display vocabulary from the helpers that produce it."""
    agg = inspect.getsource(main._compute_aggregate_status)
    literal_returns = set(re.findall(r'return "([a-z_]+)"', agg))
    assert literal_returns <= set(STATUSES), literal_returns
    declared = set(_components(_openapi())["ExamStudyPlanKnowledgeNode"]
                   ["properties"]["status"]["enum"])
    assert declared == set(main.KNOWLEDGE_LEARNING_STATUSES)
    assert declared == set(STATUSES)


def test_ab_task_enum_cannot_drift_from_the_serializer():
    src = inspect.getsource(main._compute_task_completion)
    statuses = set(re.findall(r'return \(\s*"([a-z_]+)"', src))
    targets = set(re.findall(r'return \(\s*"[a-z_]+", [^,]+, "([a-z_]+)"\)', src))
    specs = _components(_openapi())["ExamStudyPlanTaskItem"]["properties"]
    assert set(specs["computed_status"]["enum"]) == statuses
    assert set(specs["action_target"]["enum"]) == targets


def test_ab_seed_keys_are_all_modelled():
    """Every key the four seed maps can carry must exist on the models.

    Combined with the runtime tests below (which fail if a key is dropped), this means a
    future seed key cannot be silently stripped out of the response.
    """
    specs = _components(_openapi())
    seed_keys = {"0": set(), "1": set(), "2": set(), "3": set()}
    for module in MODULES:
        raw = json.loads((SEED_DIR / f"{module}_11408.json").read_text(encoding="utf-8"))

        def rec(nodes, depth):
            for node in nodes:
                seed_keys[str(min(depth, 3))] |= set(node.keys())
                rec(node.get("children") or [], depth + 1)
        rec(raw["chapters"], 0)

    chapter_fields = set(specs["ExamStudyPlanChapter"]["properties"])
    section_fields = set(specs["ExamStudyPlanSection"]["properties"])
    node_fields = set(specs["ExamStudyPlanKnowledgeNode"]["properties"])
    assert seed_keys["0"] <= chapter_fields, seed_keys["0"] - chapter_fields
    assert seed_keys["1"] <= section_fields, seed_keys["1"] - section_fields
    for depth in ("2", "3"):
        assert seed_keys[depth] <= node_fields, seed_keys[depth] - node_fields


def test_ab_no_error_models_were_added():
    """This step closes SUCCESS typing only; the error contract stays undeclared."""
    for path, method in ((GET_PATH, "get"), (PATCH_PATH, "patch")):
        assert set(_openapi()["paths"][path][method]["responses"]) <= {"200", "422"}


# ================================================================ C/D/E: runtime shape

@pytest.mark.parametrize("module", MODULES)
def test_c_every_module_returns_the_declared_top_level_shape(client, module):
    entitled_client(client, f"bc3_shape_{module}")
    r = client.get(GET_PATH.format(subject_key=module))
    assert r.status_code == 200, r.text
    body = r.json()
    assert list(body) == TOP_KEYS
    assert body["subject_key"] == module
    assert list(body["settings"]) == SETTINGS_KEYS
    assert list(body["stats"]) == STATS_KEYS
    assert isinstance(body["review_interval_days"], int)
    assert body["chapters"], f"{module}: no chapters"
    conditional = {"optional", "progress", "learned_at", "review_due_at",
                   "review_interval_days"}
    for depth, node in tree(body["chapters"]):
        assert node["is_leaf"] == (not (node.get("children") or []))
        if depth == 0:
            base = set(CHAPTER_KEYS)
        elif depth == 1:
            base = set(SECTION_KEYS)
        else:
            base = set(NODE_KEYS)
        assert base <= set(node), f"{module} depth {depth}: {base - set(node)}"
        assert set(node) - base <= conditional, \
            f"{module} depth {depth}: unexpected keys {set(node) - base}"


def test_d_new_user_payload_is_empty_but_fully_typed(client):
    entitled_client(client, "bc3_new")
    body = client.get(GET_PATH.format(subject_key="data_structure")).json()
    assert body["tasks"] == []
    assert body["settings"] == {"learning_goal": "", "start_date": "", "daily_hours": "",
                                "weekly_days": 5, "review_strategy": "sequential",
                                "show_completed": True}
    assert body["stats"]["mastered"] == 0
    assert body["stats"]["overall_status"] == "not_started"
    for _, node in tree(body["chapters"]):
        assert node["stored_status"] == "not_started"
        assert node["status"] in STATUSES
        assert "progress" not in node
        assert set(node["status_counts"]) == set(STATUSES)


def test_e_populated_payload_carries_progress_tasks_and_settings(client):
    username = entitled_client(client, "bc3_pop")
    leaves, sections = seed_leaves("data_structure")
    now = main.utc_now()
    for code, status, due in ((leaves[0], "learning", None),
                              (leaves[1], "mastered", now + timedelta(days=30)),
                              (leaves[2], "mastered", now - timedelta(days=1))):
        add_progress(username, code, status, due=due)
    db = database.SessionLocal()
    try:
        db.add(models.ExamStudyPlanTask(
            username=username, subject_key="data_structure", title="任务",
            knowledge_point_name="顺序表", scope_type="single", task_type="knowledge",
            due_date="2026-10-01", note="n"))
        db.add(models.ExamStudyPlanChapterPractice(
            username=username, subject_key="data_structure", section_code=sections[1],
            completed=True))
        db.commit()
    finally:
        db.close()

    body = client.get(GET_PATH.format(subject_key="data_structure")).json()
    assert len(body["tasks"]) == 1
    assert list(body["tasks"][0]) == TASK_KEYS
    assert body["tasks"][0]["computed_status"] in {"not_started", "in_progress", "completed"}
    assert body["tasks"][0]["action_target"] in {"knowledge_map", "practice_center"}

    progressed = [(d, n) for d, n in tree(body["chapters"]) if "progress" in n]
    assert len(progressed) == 3
    for depth, node in progressed:
        assert list(node["progress"]) == PROGRESS_KEYS
        assert node["progress"]["status"] == node["status"]
        assert isinstance(node["progress"]["review_interval_days"], int)
        assert set(node["status_counts"]) == set(STATUSES)

    # the past-due mastered point surfaces as review_due while the row stays mastered
    due_node = next(n for _, n in progressed if n["progress"]["review_due_at"]
                    and n["progress"]["stored_status"] == "mastered"
                    and n["status"] == "review_due")
    assert due_node["progress"]["status"] == "review_due"


def test_f_all_four_statuses_are_reachable_and_keep_their_shape(client):
    username = entitled_client(client, "bc3_status")
    leaves, _ = seed_leaves("data_structure")
    now = main.utc_now()
    add_progress(username, leaves[0], "not_started")
    add_progress(username, leaves[1], "learning")
    add_progress(username, leaves[2], "mastered", due=now + timedelta(days=30))
    add_progress(username, leaves[3], "review_due")

    body = client.get(GET_PATH.format(subject_key="data_structure")).json()
    seen = {n["status"] for _, n in tree(body["chapters"]) if "progress" in n}
    assert seen == set(STATUSES), seen
    for _, node in tree(body["chapters"]):
        assert node["status"] in STATUSES


def test_g_nullable_branches_are_preserved(client):
    """A row with every nullable column NULL, plus legacy/unknown raw statuses, must
    survive validation without a 500 and without being rewritten."""
    username = entitled_client(client, "bc3_null")
    leaves, _ = seed_leaves("data_structure")
    add_progress(username, leaves[0], None, system_suggested_status=None,
                 user_confirmed_status=None)
    add_progress(username, leaves[1], "已掌握", user_confirmed_status="未学习")
    add_progress(username, leaves[2], "some_future_state")
    db = database.SessionLocal()
    try:
        db.add(models.ExamStudyPlanSetting(
            username=username, subject_key="data_structure", learning_goal=None,
            start_date=None, daily_hours=None, weekly_days=None, show_completed=True))
        db.commit()
    finally:
        db.close()

    r = client.get(GET_PATH.format(subject_key="data_structure"))
    assert r.status_code == 200, r.text
    body = r.json()

    # nullable settings stay null rather than being coerced to ""
    assert body["settings"]["learning_goal"] is None
    assert body["settings"]["weekly_days"] is None
    assert body["settings"]["show_completed"] is True

    by_code = {n["progress"]["knowledge_point_code"]: n
               for _, n in tree(body["chapters"]) if "progress" in n}
    nulled = by_code[leaves[0]]
    assert nulled["status"] == "not_started"          # normalized display status
    assert nulled["stored_status"] is None            # raw NULL passes through
    assert nulled["user_confirmed_status"] is None
    assert nulled["progress"]["stored_status"] == "not_started"   # coalesced inside progress
    assert nulled["progress"]["user_confirmed_status"] == "not_started"

    legacy = by_code[leaves[1]]
    assert legacy["stored_status"] == "已掌握"          # raw legacy preserved verbatim
    assert legacy["user_confirmed_status"] == "未学习"
    assert legacy["status"] == "not_started"           # display still normalizes

    unknown = by_code[leaves[2]]
    assert unknown["stored_status"] == "some_future_state"
    assert unknown["status"] == "not_started"


def test_g_stale_progress_codes_are_not_injected_into_the_tree(client):
    """A progress row for a code the seed no longer has must not create a phantom node."""
    username = entitled_client(client, "bc3_stale")
    add_progress(username, "legacy:ghost", "mastered")
    body = client.get(GET_PATH.format(subject_key="data_structure")).json()
    codes = {n["code"] for _, n in tree(body["chapters"])}
    assert "legacy:ghost" not in codes
    assert not [n for _, n in tree(body["chapters"]) if "progress" in n]


# ================================================================ H/I: PATCH

def test_h_patch_update_returns_the_declared_shape(client):
    username = entitled_client(client, "bc3_patch")
    leaves, _ = seed_leaves("data_structure")
    code = leaves[0]
    body = patch_payload("data_structure", code, "learning", username=username)
    r = client.patch(PATCH_PATH.format(subject_key="data_structure", item_code=code),
                     json=body)
    assert r.status_code == 200, r.text
    out = r.json()
    assert list(out) == PATCH_KEYS
    assert out["success"] is True
    assert out["knowledge_point_code"] == code
    assert out["status"] == "learning"
    assert out["stored_status"] == "learning"
    assert isinstance(out["knowledge_point_title"], str)


@pytest.mark.parametrize("status", STATUSES)
def test_h_patch_accepts_every_declared_status(client, status):
    username = entitled_client(client, f"bc3_p_{status}")
    leaves, _ = seed_leaves("data_structure")
    code = leaves[0]
    r = client.patch(PATCH_PATH.format(subject_key="data_structure", item_code=code),
                     json=patch_payload("data_structure", code, status, username=username))
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["status"] == status
    assert out["status"] in STATUSES


def test_h_patch_mastered_then_due_surfaces_as_review_due_through_get(client):
    """PATCH writes the status; the GET display status follows review scheduling."""
    username = entitled_client(client, "bc3_patch_due")
    leaves, _ = seed_leaves("data_structure")
    code = leaves[0]
    r = client.patch(PATCH_PATH.format(subject_key="data_structure", item_code=code),
                     json=patch_payload("data_structure", code, "mastered",
                                        username=username))
    assert r.status_code == 200, r.text
    assert r.json()["stored_status"] == "mastered"

    body = client.get(GET_PATH.format(subject_key="data_structure")).json()
    node = next(n for _, n in tree(body["chapters"]) if n["code"] == code)
    assert node["stored_status"] == "mastered"
    assert node["status"] == "mastered"          # interval has not elapsed yet
    assert node["progress"]["review_interval_days"] >= 1


def test_i_patch_same_state_is_idempotent(client):
    username = entitled_client(client, "bc3_patch_same")
    leaves, _ = seed_leaves("data_structure")
    code = leaves[0]
    url = PATCH_PATH.format(subject_key="data_structure", item_code=code)
    payload = patch_payload("data_structure", code, "mastered", username=username)
    first = client.patch(url, json=payload)
    second = client.patch(url, json=payload)
    assert first.status_code == second.status_code == 200
    assert first.json()["status"] == second.json()["status"] == "mastered"
    assert first.json()["stored_status"] == second.json()["stored_status"] == "mastered"
    assert set(second.json()) == set(PATCH_KEYS)


# ================================================================ J/K: error contract

def test_j_invalid_module_errors_are_unchanged(client):
    entitled_client(client, "bc3_err_module")
    assert client.get(GET_PATH.format(subject_key="nope")).status_code == 400
    r = client.patch(PATCH_PATH.format(subject_key="nope", item_code="1.1"),
                     json=patch_payload("nope", "1.1", "learning", username="bc3_err_module"))
    assert r.status_code == 400
    assert r.json()["detail"] == "Unknown subject: nope"


def test_k_invalid_knowledge_code_errors_are_unchanged(client):
    username = entitled_client(client, "bc3_err_code")
    leaves, sections = seed_leaves("data_structure")
    url = PATCH_PATH.format(subject_key="data_structure", item_code="no:such:code")
    r = client.patch(url, json=patch_payload("data_structure", "no:such:code", "learning",
                                             username=username))
    assert r.status_code == 404
    assert r.json()["detail"] == "knowledge point is not in this course map"
    # a non-leaf node is a 400, not a 404
    r = client.patch(PATCH_PATH.format(subject_key="data_structure", item_code=sections[0]),
                     json=patch_payload("data_structure", sections[0], "learning",
                                        username=username))
    assert r.status_code == 400
    assert r.json()["detail"] == "Only leaf knowledge points can be manually updated"
    # unknown status is a 400
    code = leaves[0]
    r = client.patch(PATCH_PATH.format(subject_key="data_structure", item_code=code),
                     json=patch_payload("data_structure", code, "bogus", username=username))
    assert r.status_code == 400
    assert r.json()["detail"] == "Invalid status: bogus"


def test_k_unauthenticated_is_still_401(client):
    with TestClient(main.app) as anon:
        assert anon.get(GET_PATH.format(subject_key="data_structure")).status_code == 401


def test_k_unentitled_is_still_403(client):
    register_and_login(client, "bc3_free")
    r = client.get(GET_PATH.format(subject_key="data_structure"))
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "FEATURE_REQUIRES_UPGRADE"


# ================================================================ L/M: equivalence

@pytest.mark.parametrize("module", MODULES)
def test_l_get_payload_is_canonically_equivalent_to_the_untyped_route(client, module):
    entitled_client(client, f"bc3_eq_{module}")
    with TestClient(BEFORE_APP) as before:
        before.cookies = client.cookies
        old = before.get(GET_PATH.format(subject_key=module))
        new = client.get(GET_PATH.format(subject_key=module))
    assert old.status_code == new.status_code == 200
    assert canonical(old.text) == canonical(new.text), f"{module}: payload changed"


def test_l_populated_get_is_canonically_equivalent(client):
    username = entitled_client(client, "bc3_eq_pop")
    leaves, sections = seed_leaves("data_structure")
    now = main.utc_now()
    add_progress(username, leaves[0], "learning")
    add_progress(username, leaves[1], "mastered", due=now - timedelta(days=3))
    add_progress(username, leaves[2], None)
    add_progress(username, leaves[3], "已掌握", user_confirmed_status="未学习")
    db = database.SessionLocal()
    try:
        db.add(models.ExamStudyPlanTask(
            username=username, subject_key="data_structure", title="任务",
            knowledge_point_name="顺序表", scope_type="single", task_type="knowledge",
            due_date="2026-10-01", note="n"))
        db.add(models.ExamStudyPlanChapterPractice(
            username=username, subject_key="data_structure", section_code=sections[1],
            completed=True))
        db.commit()
    finally:
        db.close()
    with TestClient(BEFORE_APP) as before:
        before.cookies = client.cookies
        old = before.get(GET_PATH.format(subject_key="data_structure"))
        new = client.get(GET_PATH.format(subject_key="data_structure"))
    assert canonical(old.text) == canonical(new.text)


@pytest.mark.parametrize("status", STATUSES)
def test_l_patch_response_is_canonically_equivalent(client, status):
    username = entitled_client(client, f"bc3_eqp_{status}")
    leaves, _ = seed_leaves("data_structure")
    code = leaves[0]
    url = PATCH_PATH.format(subject_key="data_structure", item_code=code)
    payload = patch_payload("data_structure", code, status, username=username)
    with TestClient(BEFORE_APP) as before:
        before.cookies = client.cookies
        old = before.patch(url, json=payload)
        new = client.patch(url, json=payload)
    assert old.status_code == new.status_code == 200
    assert canonical(old.text) == canonical(new.text)


def test_l_error_bodies_are_canonically_equivalent(client):
    username = entitled_client(client, "bc3_eq_err")
    leaves, sections = seed_leaves("data_structure")
    cases = (
        ("GET", GET_PATH.format(subject_key="nope"), None),
        ("GET", GET_PATH.format(subject_key="data_structure"), None),
        ("PATCH", PATCH_PATH.format(subject_key="nope", item_code="1.1"),
         patch_payload("nope", "1.1", "learning", username=username)),
        ("PATCH", PATCH_PATH.format(subject_key="data_structure", item_code="no:such:code"),
         patch_payload("data_structure", "no:such:code", "learning", username=username)),
        ("PATCH", PATCH_PATH.format(subject_key="data_structure", item_code=sections[0]),
         patch_payload("data_structure", sections[0], "learning", username=username)),
        ("PATCH", PATCH_PATH.format(subject_key="data_structure", item_code=leaves[0]),
         patch_payload("data_structure", leaves[0], "bogus", username=username)),
    )
    with TestClient(BEFORE_APP) as before:
        before.cookies = client.cookies
        for method, url, body in cases:
            kw = {"json": body} if body else {}
            old = before.request(method, url, **kw)
            new = client.request(method, url, **kw)
            assert old.status_code == new.status_code, url
            assert old.text == new.text, url


def test_m_no_field_is_stripped_by_the_response_model():
    """Structural half: every key the handlers emit must exist on the model. A missing
    field would make pydantic drop it silently rather than fail."""
    assert set(TOP_KEYS) <= set(main.ExamStudyPlanResponse.model_fields)
    assert set(CHAPTER_KEYS) <= set(main.ExamStudyPlanChapter.model_fields)
    assert set(SECTION_KEYS) <= set(main.ExamStudyPlanSection.model_fields)
    assert set(NODE_KEYS) <= set(main.ExamStudyPlanKnowledgeNode.model_fields)
    assert set(PROGRESS_KEYS) == set(main.ExamKnowledgeProgressDetail.model_fields)
    assert set(TASK_KEYS) == set(main.ExamStudyPlanTaskItem.model_fields)
    assert set(SETTINGS_KEYS) == set(main.ExamStudyPlanSettings.model_fields)
    assert set(STATS_KEYS) == set(main.ExamStudyPlanStats.model_fields)
    assert set(PATCH_KEYS) == set(main.ExamKnowledgeItemUpdateResponse.model_fields)


def test_m_round_trip_preserves_every_key(client):
    """The strongest form of 'nothing stripped': the served body re-validates and dumps
    back to exactly itself."""
    username = entitled_client(client, "bc3_roundtrip")
    leaves, _ = seed_leaves("data_structure")
    add_progress(username, leaves[0], "learning")
    served = client.get(GET_PATH.format(subject_key="data_structure"))
    assert served.status_code == 200

    parsed = json.loads(served.text)
    model = main.ExamStudyPlanResponse.model_validate(parsed)
    dumped = model.model_dump(mode="json", exclude_unset=True)
    assert canonical(json.dumps(dumped)) == canonical(served.text)


# ================================================================ protected semantics

def test_typed_patch_route_still_emits_the_canonical_exam_event(client):
    """BC3 typed the response only. The canonical writer, its event ownership and the
    legacy scope id must be exactly what they were."""
    username = entitled_client(client, "bc3_semantics")
    leaves, _ = seed_leaves("data_structure")
    code = leaves[0]
    r = client.patch(PATCH_PATH.format(subject_key="data_structure", item_code=code),
                     json=patch_payload("data_structure", code, "mastered",
                                        username=username))
    assert r.status_code == 200, r.text

    from data_plane.models import LearningEvent
    session = database.SessionLocal()
    try:
        user = session.query(models.User).filter(models.User.username == username).one()
        events = (session.query(LearningEvent)
                  .filter(LearningEvent.user_id == user.id,
                          LearningEvent.event_type == "knowledge_status_changed").all())
        assert len(events) == 1
        assert events[0].service_key == "exam_prep", "must stay an exam_prep event"
        assert events[0].subject_key == "cs_408", "event subject is the EXAM subject"
        ctx = json.loads(events[0].knowledge_point_ref_json)
        assert ctx["exam_module_id"] == "data_structure"
        assert "exam_track_id" not in ctx, "the track never enters an event"

        row = (session.query(models.UserKnowledgeProgress)
               .filter(models.UserKnowledgeProgress.username == username,
                       models.UserKnowledgeProgress.knowledge_point_code == code).one())
        assert row.course_id == "data_structure_11408", "legacy scope id preserved"
        assert row.knowledge_point_id == 0, "the writer's sentinel is unchanged"
    finally:
        session.close()


def test_repeat_write_of_the_same_status_emits_nothing(client):
    """Same-state behaviour is a product semantic BC3 must not have altered."""
    username = entitled_client(client, "bc3_same_state_event")
    leaves, _ = seed_leaves("data_structure")
    code = leaves[0]
    url = PATCH_PATH.format(subject_key="data_structure", item_code=code)
    payload = patch_payload("data_structure", code, "learning", username=username)
    assert client.patch(url, json=payload).status_code == 200
    assert client.patch(url, json=payload).status_code == 200

    from data_plane.models import LearningEvent
    session = database.SessionLocal()
    try:
        user = session.query(models.User).filter(models.User.username == username).one()
        events = (session.query(LearningEvent)
                  .filter(LearningEvent.user_id == user.id,
                          LearningEvent.event_type == "knowledge_status_changed").all())
        assert len(events) == 1, "a repeated status must not emit a second transition"
    finally:
        session.close()


# ================================================================ generated TS

GENERATED_TS = Path(__file__).resolve().parents[2] / "frontend" / "src" / "types" / "api.ts"


def test_generated_typescript_knowledge_responses_are_not_unknown():
    if not GENERATED_TS.exists():
        pytest.skip("frontend api.ts not generated in this checkout")
    src = GENERATED_TS.read_text(encoding="utf-8")
    if f'components["schemas"]["{GET_MODEL}"]' not in src:
        pytest.skip("run `npm run api:generate` to refresh frontend/src/types/api.ts")
    for model in (GET_MODEL, PATCH_MODEL, "ExamStudyPlanChapter", "ExamStudyPlanSection",
                  "ExamStudyPlanKnowledgeNode", "ExamStudyPlanSettings",
                  "ExamStudyPlanStats", "ExamStudyPlanTaskItem"):
        assert f'components["schemas"]["{model}"]' in src, model

    for op, model in (
        ("get_exam_subject_study_plan_exam_11408_subjects__subject_key__study_plan_get",
         GET_MODEL),
        ("update_exam_study_plan_knowledge_item_exam_11408_subjects__subject_key__"
         "study_plan_knowledge_items__item_code__patch", PATCH_MODEL),
    ):
        assert op in src, op
        block = src[src.index(f"{op}: {{"):]
        block = block[:block.index("422:")]
        assert f'components["schemas"]["{model}"]' in block, op
        assert '"application/json": unknown' not in block, op
