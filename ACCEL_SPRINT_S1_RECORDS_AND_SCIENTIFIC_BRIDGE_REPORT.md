# ACCEL_SPRINT_S1 — F1C6 Learning Record Closure + Scientific Runtime Product Bridge

Date: 2026-09-19. Repository: `C:\Users\26477\Desktop\ai_study_platform`.
Mode: accelerated backend productization. **No frontend UI was implemented.**

```text
ACCEL_SPRINT_S1_COMPLETE
```

Every number below was measured against a TEMP copy of the database with real
authenticated sessions and real business actions. `backend/app.db` was opened `?mode=ro`
only and is byte-identical to its pre-sprint state (§ K).

---

## A. F1C6 learning record closure

### A1 — UTC timestamp fix

**Defect (confirmed from source, not assumed).** SQLite returns `submitted_at` as a NAIVE
datetime holding a UTC wall-clock. `naive_datetime.timestamp()` interprets a naive value
as SERVER-LOCAL time, so every practice-derived event was stamped 8 hours early on this
UTC+8 host (and would be invisible on a UTC host — machine-dependent data).

Six conversion sites carried the defect. All now route through ONE shared module:

| site | role |
| --- | --- |
| `backend/core/timeutil.py` **(new)** | the single UTC conversion path |
| `backend/data_plane/emitter.py` | `course_practice` live emit |
| `backend/data_plane/backfill.py` | `course_practice` backfill |
| `backend/learning/practice/events.py` | practice + past-paper bridge |
| `backend/learning/records/producers.py` | knowledge / material / AI producers |
| `backend/learning/records/backfill.py` | records backfill |
| `backend/learning/records/service.py` | read side (now delegates, was already UTC-correct) |

```text
TIMESTAMP_UTC_FIX = YES (6 sites → 1 shared conversion, core/timeutil.py)
SAME_REAL_MOMENT_EVENT_TIME_DRIFT = 0.000 s   (hard gate: <= 1 s)
```

Measured: knowledge, practice, past-paper and AI/audit producers were each given the SAME
real moment (`2026-09-19T03:04:05.25Z`); all four recorded it within 0 s of each other and
within 0 s of the true epoch. Test: `test_same_real_moment_has_no_cross_producer_drift`.

### A2 — AI audit events are not study history

`ai_called` / `source_type=ai_request` is a real accounting fact and is **preserved
untouched** in `learning_events`. The taxonomy now classifies visibility explicitly
(`USER_FACING` / `AUDIT_ONLY`), and the canonical read surface excludes audit-only types
**server-side** by default:

```text
AI_AUDIT_EVENT_USER_FACING = NO
```

* default list/`summary`/exam-timeline responses never contain an audit event;
* `?include_audit=true` is the explicit opt-in that reaches them (they are not deleted);
* asking for an audit `event_type`/`category` *without* the flag is a **400**, not a
  silent empty page — the contract states the rule instead of leaving the client to guess;
* the detail route refuses an audit-only event id unless the flag is passed;
* the frontend therefore never needs `if event_type == "ai_called": hide`.

### A3 — the contested `/learning-records` prefix

Before: `GET /learning-records/{event_id}` was registered first and swallowed the legacy
`GET /learning-records/stats`, which answered `404 {"detail":"record not found"}` from the
**canonical** handler. Two id spaces (UUID events vs integer notebook records) shared one
prefix.

After:

```text
CANONICAL_RECORD_ROUTE_AMBIGUITY = 0
ROUTE_PREFIX_CONFLICT = RESOLVED
```

* the canonical detail route matches a **canonical UUID only** (`{event_id:uuid}`), so a
  literal sibling path can never be captured as an event id;
* the legacy `GET /learning-records/stats` is **reachable again** (measured `200`);
* legacy `POST` / `PATCH` / `DELETE /learning-records/{record_id}` are untouched — no
  legacy consumer breaks (the existing legacy contract test suite still passes);
* **one explicit canonical exam-scoped timeline** was added:
  `GET /exam/prep/records` — literal-path, unambiguous, module-filterable.

### A4 — unanswered semantics

`UNANSWERED != INCORRECT` was already enforced for `correct`. It was **not** enforced for
`score`: the legacy past-paper writer records `score: 0` for a blank, and the mirror copied
it, so a record read alone as "0 分" for a question never answered.

Fixed at both boundaries, mirroring the existing `_ungraded_to_none` design:

* write boundary — `learning/practice/adapters/exam.py`: a blank answer means no
  authoritative score, so `score`/`max_score` cross as `null`;
* event boundary — `learning/practice/events.py`: a blank answer forces `correct=null` and
  `score=null` for ANY practice-derived event;
* read boundary — `records/service.py`: defense in depth for rows written before the fix.

```text
UNANSWERED_SCORE_ZERO = 0
```

A **genuinely graded zero** (an answer IS present and scored 0) passes through untouched —
asserted in the same test.

### A5 — bounded summary

`summarize_records` previously did `q.all()` over every event for the user and derived
every figure in Python — unbounded memory in the user's history length.

Now every figure is a SQL aggregate (`COUNT` / `GROUP BY`, with the factual tri-state split
computed in SQL). The summary materializes at most one row per event type, never one row
per event.

```text
SUMMARY_BOUNDED = YES (SQL COUNT + GROUP BY; no row materialization)
```

`ai_calls` was removed from the summary: the summary is a study-history summary and audit
facts are not study history (A2). Semantics of every remaining figure are unchanged.

### A6 — canonical timeline contract

Unchanged where it was already correct, and now stated explicitly:

```text
USER-FACING (the timeline)     question_answered · course_practice · code_submitted ·
                               knowledge_status_changed · material_opened · material_asked
AUDIT-ONLY (never in a timeline)  ai_called
DEFERRED (no producer, never synthesized)  wrong_answer_resolved · plan_created ·
                               task_completed · review_completed
```

No `wrong_created` / `wrong_resolved` event was invented: wrong state is a projection
rebuilt from practice facts. The frontend may honestly present a `question_answered` record
with `summary.correct == false` as an incorrect attempt. No plan history is fabricated.

### A7 — typed paginated API

Every record operation now declares a concrete response model
(`learning/records/contract.py`), so the generated client stops seeing `unknown`:

| operation | response model |
| --- | --- |
| `GET /learning-records` | `RecordPage` |
| `GET /learning-records/{event_id}` | `RecordDetail` |
| `GET /learning-records/summary` | `RecordsSummaryResponse` |
| `GET /learning-records/taxonomy` | `RecordsTaxonomyResponse` |
| `GET /exam/prep/records` | `RecordPage` |

```text
RECORD_REQUIRED_REQUEST_UNKNOWN = 0
RECORD_REQUIRED_SUCCESS_UNKNOWN = 0   (was 2; summary/taxonomy are typed too)
CURSOR_PAGINATION = YES — stable, deterministic tie-break, no overlap, no missing row
```

`limit` is bounded (`ge=1, le=200`); an invalid cursor is a 400. A test asserts the declared
models cover **every** summary field any producer actually emits, so a new factual field
breaks the test rather than silently vanishing from the contract.

**Also closed (same defect class):** the exam module filter is applied **in SQL before
pagination** (`json_extract(..., '$.exam_module_id')`), so a module-scoped page is correct
and full; an unknown module is a **400**, never a silently unfiltered page. The course view
had the identical bug (filtering `course_id` *after* pagination, which returns short pages
and skips matching rows on the next cursor) — it is now a SQL filter on the event's own
`course_id` column.

### Canonical endpoints

```text
LEARNING_RECORD_CANONICAL_ENDPOINT = GET /learning-records          (product timeline)
                                   + GET /exam/prep/records         (canonical exam / CS408
                                                                     timeline, module-scoped)
```

---

## B. Scientific Runtime product bridge

### B1 — the hard boundary

The Product Backend never imports the scientific stack. Two independent proofs ship as
tests:

* **source proof** — a scan of every non-test `.py` under `backend/` for
  `torch` / `transformers` / `faiss` / `zhixue_runtime` / `sentence_transformers` /
  `sklearn` finds zero offenders;
* **runtime proof** — importing the application loads none of them into `sys.modules`
  (they are not even installed in `backend/.venv`, so the product runs without the stack).

```text
SCIENTIFIC_RUNTIME_BRIDGE = backend/science/  (HTTP only)
PRODUCT_BACKEND_HEAVY_IMPORTS = NONE
```

There is exactly ONE HTTP client: `backend/science/client.py`. The pre-existing
evidence-pipeline client (`data_plane/runtime_client.py`) had its own `httpx.post`; it now
**delegates transport** to `science.client` and keeps only what is genuinely specific to it
(LearningEvent mapping, canonical input hash, strict response validation). A test asserts
no scientific module performs its own HTTP.

The client provides: base URL from config (`SCIENTIFIC_RUNTIME_BASE_URL`, default
`http://127.0.0.1:8101`), a bounded wall-clock timeout (`SCIENTIFIC_RUNTIME_TIMEOUT`,
default 10 s), a per-call correlation `request_id`, a response-size cap, and a two-way
bounded failure taxonomy — `ScientificUnavailable` (transport/timeout/5xx/non-JSON) and
`ScientificRejected` (4xx = our bug, not an outage).

### B2 — shared authority metadata

Every product-facing scientific response carries the same block
(`backend/science/metadata.py`), declared concretely in OpenAPI as `ScientificAuthority`:

```text
component · mode · controls_product_decision · writes_learner_fact · generated_at ·
request_id · runtime_release_id · source_class · latency_ms · blockers[] · semantics
```

`controls_product_decision` and `writes_learner_fact` are constants (`false`), not
parameters. No scientific preview mutates learner facts (asserted by before/after
snapshots in tests).

### The runtime side

Two inference endpoints were added to the Scientific Runtime Service — the only process
allowed to touch the models:

* `POST /v1/inference/misconception-v2`
* `POST /v1/inference/tutor-policy`

`/v1/capabilities` now reports `["student_twin", "misconception_v2", "tutor_policy"]`.

**The runtime release id was deliberately NOT bumped.** Serving additional components over
HTTP changes no scientific computation, no model asset and no StudentTwin numeric; the id
is part of frozen provenance (it is written onto every Prediction row and names the
shipped deploy artifact under `deploy/artifacts/`). Bumping it would have invalidated
recorded provenance and required rebuilding a preservation-critical artifact for no
scientific change. The capability set is reported by `/v1/capabilities` instead.

`zhixue_runtime` errors derive from `ZhixueRuntimeError`, **not** from `ValueError`; the
bridge translates them so an invalid caller action is a **422** and a missing model asset
is a bounded **503** — never an unhandled 500.

---

## C. Student Twin product integration V1

### C1/C2 — endpoint

```text
STUDENT_TWIN_ENDPOINT = GET /exam/prep/scientific/student-twin
                        (?exam_module_id=… optional; unknown module → 400)
```

Input is built **only** from the caller's real canonical events: the same
`learning_events` stream the records API reads. No LLM-generated state, no re-derivation,
no reimplementation of Student Twin in the Product Backend — the request is sent to
`POST /v1/inference/student-twin` on the runtime.

Only families carrying a factual correctness measurement are sent
(`course_practice`, `question_answered`, `code_submitted`); an ungraded item carries no
evidence, and an absent field stays absent rather than being defaulted. The request is
bounded to the most recent 2000 events. The `user_ref` sent to the runtime is an opaque
salted hash — the runtime needs an identity, not a person.

### C3 — semantics

Student Twin is a **deterministic rule-based state engine**, not a neural model. The
contract never uses 掌握度模型 / AI预测模型 / 神经网络 vocabulary, and the response carries
an explicit `semantics` string stating it is a deterministic replay that controls no
product decision.

```text
STUDENT_TWIN_MODE = PREVIEW
STUDENT_TWIN_CONTROLS_PRODUCT_DECISION = false
```

### C4 — no state mutation

Verified by before/after snapshot of `learning_events`, `wrong_answer_states` and
`user_knowledge_progress` across a preview call: **identical**. Knowledge status, mastery,
wrong-answer state, plan status and grades are untouched.

### Honest scope statement (a blocker, not hidden)

The frozen taxonomy (`learning.records.taxonomy`) marks `course_practice` as the ONLY
StudentTwin-eligible family; CS408 practice records are `question_answered`, which the
frozen taxonomy marks **not** eligible. The preview therefore computes on **real** facts
but always attaches the blocker:

```text
INPUT_FAMILY_NOT_STUDENT_TWIN_ELIGIBLE: question_answered
```

It is labelled an EXPERIMENT view, writes nothing, controls nothing, and the fact is stated
rather than silently ignored. Closing that eligibility question is a Productization Gate
decision (Domain Compatibility) and is **not** taken in this sprint.

### Governance note (reported, not self-decided)

SSOT §54 / STEP6 freeze `student_twin` as `MVP_TARGET = SHADOW_ONLY` with
`MVP_USER_VISIBLE_FEATURE = NONE`. This sprint's brief explicitly requests the first
Product Backend → Scientific Runtime bridge with a 学习状态实验视图, which is a user-visible
surface. The brief (the user's latest explicit decision) is the higher authority under
SSOT §0.1, so it was implemented as an experiment preview that controls nothing — and the
delta is **reported here rather than written into the SSOT**. SSOT §74 authorises an update
only on an explicit product-direction change; that is the user's call.

---

## D. misconception_v2 advisory integration

### D1 — the real contract (inspected, not assumed)

The adapter is `DualEncoder` (BGE-M3, mean-pool + L2) → `faiss.normalize_L2` →
`IndexFlatIP.search`. Query template: `"{question} [ANS] {answer}"`. Ontology: **2587 Eedi
misconceptions, English**. No retraining, and the model stack is never imported into the
Product Backend — the call is HTTP.

### D2 — product use case

```text
MISCONCEPTION_ENDPOINT = POST /science/misconception-advisory?state_id=…&top_k=3
```

The learner explicitly asks; nothing runs in the background. The Product Backend loads the
factual question and wrong-answer context from the canonical wrong-answer record
(`wrong_answers.service.state_detail`) and the question text from the table that owns it
(`exam_question_bank`). Ownership is enforced by the canonical owner: a cross-user state id
answers **404**, never an existence oracle.

### D3 — semantics are preserved

```text
MISCONCEPTION_SCORE_SEMANTICS = similarity (cosine-like normalized inner product);
                                NOT probability, NOT confidence, NOT P(misconception),
                                NOT diagnosis certainty
```

The field is named `similarity`. The candidate shape is exactly
`{rank, candidate_id, candidate_label, similarity}`; the OpenAPI schema contains no
`probability` / `confidence` / `score` property, and a test asserts every textual
occurrence of "probability" in the response appears only inside a negation.

### D4 — no learner-state write

```text
MISCONCEPTION_ADVISORY_WRITES_LEARNER_FACT = 0
```

Verified by before/after snapshot: `wrong_answer_states` (id, status, wrong_count),
`learning_events` count and `user_knowledge_progress` count are identical across an
advisory call.

### D5 — domain / ontology gate

The audit identified two independent blockers, and neither was worked around:

1. **`ONTOLOGY_MISMATCH`** — the runtime ontology (Eedi, 2587, English) is a *different*
   ontology from the product's (Chinese CS/11408); the adapter itself documents the mapping
   as unresolved. The productization matrix in `data_plane/eligibility.py` already froze
   `misconception_v2 = ONTOLOGY_MISMATCH`. No mapping was fabricated.
2. **`RUNTIME_COMPONENT_NOT_PROVISIONED`** — the deployed runtime environment
   (`D:\ZhixueAI\envs\runtime-service`) ships `numpy` but **not** `torch` /
   `transformers` / `faiss`, so the component cannot execute there. This is documented in
   `scientific_runtime_service/requirements.txt` as component-scoped extras rather than
   blind-pinned.

```text
MISCONCEPTION_PRODUCT_MODE = SHADOW_NOT_USER_VISIBLE
MISCONCEPTION_ADVISORY_MODE = SHADOW_NOT_USER_VISIBLE   (no ACTIVE, no ADVISORY this sprint)
```

The bridge is nevertheless **wired and proven**: when the runtime answers, the real
retrieval path is exercised end-to-end through the real runtime FastAPI application, and
the result is labelled SHADOW_NOT_USER_VISIBLE with the exact blocker attached.

---

## E. tutor_policy shadow hook

### E1 — hook established, target mode SHADOW

The runtime endpoint exists (`POST /v1/inference/tutor-policy`), the product hook exists
(`backend/science/tutor_policy.py`) and is proven end-to-end by a test that supplies an
explicit turn state. The router reports it at `GET /science/tutor-policy`.

### E2 — the exact blocker (not fabricated)

The model needs `FULL_STATE`: problem, the student's wrong solution, a student profile, a
teacher-described confusion, the **prior pedagogical actions**, and the dialogue. Two
inputs cannot be formed from real product facts:

```text
TURN_STATE_PREV_ACTIONS_UNAVAILABLE
  the product records no pedagogical-action history per turn, so prev_actions has no
  honest value — and it is the model's DOMINANT input signal (dialogue + previous actions)

TURN_STATE_RESEARCH_FIELDS_UNAVAILABLE
  'profile' (student profile) and 'confusion' (teacher-described confusion) are
  research-dataset fields with no product source

TURN_STATE_NOT_A_TUTOR_TURN
  the CS408 AI surface exposes one-shot question explanation, not a tutoring dialogue with
  a submitted wrong solution
```

This matches the frozen `data_plane/eligibility.py` entry
(`tutor_policy = MISSING_INPUT` / `UNRESOLVED`). `build_turn_state` returns `None` plus the
blockers; **nothing is fabricated** and the runtime is not called with invented input.

The 4-way ontology is preserved exactly (`focus / generic / probing / telling`) and read
back from the runtime rather than assumed.

```text
TUTOR_POLICY_PRODUCT_MODE = SHADOW
TUTOR_POLICY_CONTROLS_RESPONSE = false
```

The hook is **not on the response path**: nothing in the tutor/chat flow consumes it, and a
test asserts the orchestrator does not reference `tutor_policy` at all. There is nothing to
disable — the suggestion cannot change a reply.

---

## F. Failure isolation

```text
SCIENTIFIC_FAILURE_ISOLATED = YES
```

With the runtime made to refuse every connection, measured in one test:

* `GET /exam/prep/scientific/student-twin` → **200** with `mode = UNAVAILABLE` and
  `blockers = ["…SCIENTIFIC_RUNTIME_UNAVAILABLE"]` — a bounded state, not an error;
* misconception advisory → **200** with `available: false` and the same blocker;
* core learning loop, all still **200**: `/learning-records`, `/exam/prep/records`,
  `/practice/sessions` (read and create), `/wrong-answers`;
* no **500** anywhere.

The same holds for a timeout and for a non-JSON response — both are bounded
`ScientificUnavailable` outcomes, asserted directly at the client boundary.

---

## G. Security / privacy

* **No private payload leakage into records.** The record view is unchanged in what it
  exposes (references and factual metrics only); the audit exclusion (A2) *removes* the one
  ops-telemetry family from the learner timeline. `envelope.assert_payload_is_safe` still
  actively rejects payloads carrying prompt/response/answer text/code/paths.
* **Scientific endpoints are authenticated.** Anonymous → 401/403 on all three.
* **Cross-user isolation.** User B requesting user A's wrong-answer state id → **404**;
  user B's own Student Twin preview reports `event_count = 0` even while A has events.

```text
CROSS_USER_RECORD_ACCESS = 0
CROSS_USER_SCIENTIFIC_ACCESS = 0
```

---

## H. OpenAPI / generated TypeScript

All new product-facing endpoints declare concrete request and response models.

```text
SCIENTIFIC_REQUIRED_REQUEST_UNKNOWN = 0
SCIENTIFIC_REQUIRED_SUCCESS_UNKNOWN = 0
RECORD_REQUIRED_REQUEST_UNKNOWN = 0
RECORD_REQUIRED_SUCCESS_UNKNOWN = 0
```

Regenerated with the project's own tooling and **no hand edits**:

1. copy `backend/app.db` → `.f1c6tmp/s1_temp.db` (never the real DB);
2. `alembic upgrade head` on the copy → `20260919_0009`;
3. standalone uvicorn on **port 8947** (not 8000) with an explicit `DATABASE_URL` pointing
   at the copy;
4. `npx openapi-typescript@7.13.0 <temp>/openapi.json -o src/types/api.ts`.

Measured on the resulting document: all 8 required operations carry a `$ref` 200 schema and
have zero untyped parameters (327 paths total).

The regenerated `api.ts` also picks up the STEP-7 routers that the previously committed
file had never seen (`/practice/*`, `/wrong-answers/*`, `/exam/prep/*`,
`/subscription/*`, `/usage/*`, `/ai-models`) — pre-existing working-tree drift, expected
and reported rather than hidden.

---

## I. Test matrix

All 16 required cases exist and pass in
`backend/tests/test_s1_records_and_scientific_bridge.py` (28 tests):

| # | case | test |
| --- | --- | --- |
| 1 | UTC timestamp consistency | `test_same_real_moment_has_no_cross_producer_drift`, `test_naive_persisted_timestamp_is_read_as_utc` |
| 2 | AI audit excluded from user timeline | `test_ai_audit_never_reaches_the_user_timeline` |
| 3 | canonical route not shadowed | `test_canonical_record_route_does_not_shadow_literal_paths`, `test_exam_scoped_timeline_is_module_filterable` |
| 4 | unanswered score null | `test_unanswered_item_carries_no_score`, `test_unanswered_score_is_not_zeroed_at_the_attempt_boundary` |
| 5 | bounded summary | `test_summary_is_bounded_by_sql_aggregates` |
| 6 | cursor pagination stable | `test_cursor_pagination_is_stable_and_module_scoped` |
| 7 | cross-user record isolation | `test_records_are_isolated_per_user` |
| 8 | Student Twin real runtime HTTP contract | `test_student_twin_speaks_the_real_runtime_http_contract`, `test_student_twin_request_satisfies_runtime_validation` |
| 9 | Student Twin no product-state mutation | `test_student_twin_preview_writes_no_learner_fact` |
| 10 | runtime unavailable does not break core flows | `test_scientific_outage_does_not_break_core_flows`, `test_scientific_base_url_and_timeout_are_configurable` |
| 11 | misconception advisory/shadow contract | `test_misconception_advisory_contract_and_shadow_mode`, `test_misconception_stays_shadow_when_the_runtime_is_unprovisioned` |
| 12 | misconception score as similarity only | `test_misconception_exposes_similarity_only` |
| 13 | misconception no learner-state write | `test_misconception_advisory_writes_no_learner_fact` |
| 14 | tutor_policy cannot control a response | `test_tutor_policy_shadow_cannot_control_a_response`, `test_tutor_policy_bridge_works_and_stays_shadow`, `test_tutor_policy_is_not_wired_into_any_response_path` |
| 15 | cross-user scientific isolation | `test_scientific_endpoints_are_authenticated_and_user_scoped` |
| 16 | OpenAPI concrete | `test_new_contracts_are_concrete_in_openapi`, `test_declared_record_models_cover_every_emitted_summary_field` |
| B1 | boundary + one client | `test_product_backend_imports_no_scientific_stack`, `test_the_product_backend_process_has_not_loaded_a_scientific_stack`, `test_only_one_scientific_http_client_owns_transport` |

**Doubles are placed below the HTTP/runtime boundary only:**

* runtime side — `runtime_bridge.replay_state` / `misconception_matches` /
  `tutor_policy_action` are stubbed **inside** the runtime service, so the REAL FastAPI
  runtime application still performs its own request validation and response serialization;
* product side — an `httpx.MockTransport` at the **transport layer**, so real request
  building, timeout handling, status handling and response parsing all run.

No paid external provider is called. The StudentTwin scientific formula is never
reimplemented in a double.

The runtime service's own suite also gained 6 tests for the two new endpoints (validation,
similarity-not-probability, bounded 503 on a missing asset, the frozen 4-way ontology, 422
for an out-of-ontology action).

---

## J. Regression

```text
TARGETED_TESTS = 28 passed / 0 failed   (test_s1_records_and_scientific_bridge.py)
RUNTIME_SERVICE_TESTS = 20 passed / 0 failed   (real runtime venv, real StudentTwin replay)
FULL_BACKEND_TESTS = 1211 collected / 1211 passed / 0 failed
```

Run with the project venv (`backend/.venv/Scripts/python.exe -m pytest`), matching the
CLAUDE.md requirement. Three failures found in the first full run were fixed rather than
tolerated:

1. `test_runtime_client` — the transport seam moved to `science.client`, so the old
   `monkeypatch(httpx.post)` double no longer applied; the tests were re-pointed at
   `httpx.MockTransport` (same coverage, plus a new connection-refused case);
2. `test_data_producer` — asserted the old runtime release id; reverted with the release
   id (see § B);
3. `test_course_ai_migration::test_free_user_course_ai_e2e` — asserted `ai_called` appears
   in the **user-facing** course timeline. That expectation is exactly what A2 forbids, so
   the test now asserts the audit fact is *absent from the timeline and present in the
   database*.

Frontend (no UI implemented, contract regeneration only):

```text
FRONTEND_TYPECHECK = passed (tsc --noEmit)
FRONTEND_LINT = passed (eslint .)
FRONTEND_UNIT_TESTS = passed (22 files / 78 tests)
FRONTEND_BUILD = passed (✓ built in 431ms)
```

---

## K. Real database safety

`backend/app.db` was opened read-only, and every probe/run used a TEMP copy.

| | before | after |
| --- | --- | --- |
| SHA256 | `1c1b2d85…3fe522` | `1c1b2d85…3fe522` |
| size | 64917504 | 64917504 |
| mtime | 2026-09-16 21:24:23 | 2026-09-16 21:24:23 |
| tables | 72 | 72 |
| `PRAGMA integrity_check` | ok | ok |

```text
REAL_APP_DB_MUTATED = NO
```

No migration was needed for this sprint: every change is additive or read-side, and
`learning_events` already arrives through `alembic upgrade head` (head unchanged at
`20260919_0009`). The real `app.db` still does not contain `learning_events`, so the records
surface is empty there by construction, not by lack of use.

---

## Final gates

```text
ACCEL_SPRINT_S1_COMPLETE

LEARNING_RECORD_CANONICAL_ENDPOINT = GET /learning-records  (+ GET /exam/prep/records, the
                                     canonical exam/CS408 module-scoped timeline)
TIMESTAMP_UTC_FIX = YES (6 sites → 1 shared conversion in core/timeutil.py)
AI_AUDIT_EVENT_USER_FACING = NO (excluded server-side; fact preserved; include_audit opt-in)
ROUTE_PREFIX_CONFLICT = RESOLVED (detail matches UUID only; legacy /learning-records/stats
                                   reachable again; canonical exam timeline added)
UNANSWERED_SCORE_ZERO = 0
SUMMARY_BOUNDED = YES (SQL COUNT + GROUP BY; no row materialization)
CURSOR_PAGINATION = YES (stable, deterministic tie-break, no overlap)

SCIENTIFIC_RUNTIME_BRIDGE = backend/science/ — ONE HTTP client (client.py), typed requests
                            and responses, correlation id, bounded timeout, bounded failure
PRODUCT_BACKEND_HEAVY_IMPORTS = NONE (source scan + sys.modules proof; not even installed)

STUDENT_TWIN_ENDPOINT = GET /exam/prep/scientific/student-twin
STUDENT_TWIN_MODE = PREVIEW
STUDENT_TWIN_CONTROLS_PRODUCT_DECISION = false

MISCONCEPTION_ENDPOINT = POST /science/misconception-advisory
MISCONCEPTION_PRODUCT_MODE = SHADOW_NOT_USER_VISIBLE
MISCONCEPTION_SCORE_SEMANTICS = similarity (cosine-like normalized inner product);
                                NOT probability, NOT confidence, NOT a diagnosis
MISCONCEPTION_WRITES_LEARNER_FACT = 0

TUTOR_POLICY_PRODUCT_MODE = SHADOW
TUTOR_POLICY_CONTROLS_RESPONSE = false

SCIENTIFIC_FAILURE_ISOLATED = YES (bounded UNAVAILABLE; core loop unaffected; no 500)

RECORD_REQUIRED_REQUEST_UNKNOWN = 0
RECORD_REQUIRED_SUCCESS_UNKNOWN = 0
SCIENTIFIC_REQUIRED_REQUEST_UNKNOWN = 0
SCIENTIFIC_REQUIRED_SUCCESS_UNKNOWN = 0

TARGETED_TESTS = 28 passed / 0 failed
FULL_BACKEND_TESTS = 1211 passed / 0 failed

FRONTEND_TYPECHECK = passed
FRONTEND_LINT = passed
FRONTEND_UNIT_TESTS = passed (78)
FRONTEND_BUILD = passed

REAL_APP_DB_MUTATED = NO

F1C6_FRONTEND_READY = YES
SCIENTIFIC_FRONTEND_READY = PARTIAL
  student_twin preview  READY  (typed, PREVIEW, controls nothing)
  misconception advisory READY to build, NOT to show (SHADOW_NOT_USER_VISIBLE until the
                         ontology question is resolved)
  tutor_policy          NOT READY (SHADOW; reports its own blocker; controls no response)

BLOCKERS =
  1. STUDENT_TWIN input scope: the frozen taxonomy marks course_practice as the only
     StudentTwin-eligible family, so a question_answered (CS408) preview always carries
     INPUT_FAMILY_NOT_STUDENT_TWIN_ELIGIBLE. Closing it is a Productization Gate
     (Domain Compatibility) decision, not made here.
  2. MISCONCEPTION ontology: runtime ontology is Eedi/English (2587); the product ontology
     is Chinese CS/11408. No honest mapping exists → SHADOW_NOT_USER_VISIBLE.
  3. MISCONCEPTION provisioning: the runtime environment installs numpy but not
     torch/transformers/faiss, so the component cannot execute in the current deployment.
     Declared as component-scoped extras in scientific_runtime_service/requirements.txt.
  4. TUTOR_POLICY turn state: no pedagogical-action ledger and no research profile/confusion
     fields exist in the product, and the CS408 AI surface is one-shot, not a dialogue →
     input cannot be formed honestly. Reported, not fabricated.
  5. GOVERNANCE (needs a user decision, not a code change): STEP6/SSOT §54 freeze
     student_twin with MVP_USER_VISIBLE_FEATURE = NONE. This sprint's brief explicitly asks
     for the first bridge with a 学习状态实验视图. Implemented per the brief as a
     non-controlling experiment view; the SSOT was NOT rewritten. Updating it requires the
     §74 condition (an explicit product-direction change).
  6. NOT CLOSED, OUT OF SCOPE: the record timeline still has no `total` count, and a
     past-paper record does not carry the paper's `year` for a complete public deep link.
     Both were listed as optional in the F1C6A audit and are untouched here.
```

## What was NOT done

No frontend UI. No wrong-answer or plan event type (both honestly absent by design). No
study-time estimates, streaks, heatmaps, mastery trends, readiness scores or AI summaries.
No schema change, no migration, no event redesign, no SSOT edit. No scientific model was
retrained, and no scientific formula was reimplemented in the Product Backend. No paid
provider was called.
