# ACCEL_SPRINT_S4 — MULTI-COMPONENT SCIENTIFIC PRODUCTIZATION + PRODUCTION DATA-PLANE MIGRATION READINESS

**Verdict: COMPLETE.**

Frozen baseline at entry: `ACCEL_FRONTEND_S2 = FROZEN`, `ACCEL_SPRINT_S3 = FROZEN`,
`FULL_BACKEND_TESTS = 1257 passed / 0 failed`, `FRONTEND_UNIT_TESTS = 82 passed`.
Real database (`backend/app.db`) = **READ ONLY** throughout. `REAL_APP_DB_MUTATED = NO`.

This sprint was deliberately multi-component. It did not attempt to force a blocked model
through its gate. Every component was audited against its REAL source and the REAL product
schema, and each was then either productized (none qualified) or left in its honest mode
with an exact blocker list.

**Net result: the only user-visible scientific capability remains `student_twin`.**
`USER_VISIBLE_PREVIEW = 1`, unchanged. What the sprint DID add is two real product surfaces
that state their gates precisely instead of fabricating a number, plus a proven migration
path to HEAD for the production database.

---

## 0. SCOPE — FILES CHANGED

| File | Change |
|---|---|
| `ZHIXUE_AI_PRODUCT_REDESIGN_SSOT.md` | §49 CURRENT Scientific Runtime inventory refreshed (PART A) |
| `scientific_runtime_service/README.md` | endpoint table corrected (directly related current-state doc) |
| `docs/architecture/PYTHON_AI_BACKEND_ARCHITECTURE.md` | runtime service structure line corrected |
| `scientific_runtime_service/app/config.py` | `evidence_reliability` added to `COMPONENT_IDS` + frozen source identity |
| `scientific_runtime_service/app/contracts.py` | `EvidenceReliabilityRequest` / `…Response` DTOs |
| `scientific_runtime_service/app/runtime_bridge.py` | `evidence_reliability_panel()` + pinned semantics constant |
| `scientific_runtime_service/app/main.py` | `POST /v1/inference/evidence-reliability` |
| `scientific_runtime_service/tests/test_api.py` | component list updated + 7 endpoint tests |
| `scientific_runtime_service/tests/test_evidence_reliability_real_model.py` | **new** — real-checkpoint execution |
| `backend/science/evidence_reliability.py` | **new** — gated capability report (no number produced) |
| `backend/science/capabilities.py` | **new** — 13-component product-readiness registry |
| `backend/science/contract.py` | `EvidenceReliability*` + `ScientificCapabilit*` response models |
| `backend/routers/exam_prep.py` | `GET /scientific/evidence-reliability`, `GET /scientific/capabilities` |
| `backend/tests/test_s4_scientific_productization.py` | **new** — 33 tests |
| `backend/tests/test_s4_migration_readiness.py` | **new** — 13 tests |
| `frontend/src/types/api.ts` | regenerated (no hand edits) |

No file under `backend/ai/`, `backend/data_plane/`, `backend/learning/`, `backend/database.py`
or `migrations/` was modified. **No migration was added or altered.**

---

## PART A — SSOT CURRENT SCIENTIFIC RUNTIME REFRESH

`SSOT_SCIENTIFIC_RUNTIME_CURRENT_UPDATED = YES`

§49 said the service had exactly three routes. It has seven:

```text
/health
/v1/capabilities
/v1/inference/student-twin
/v1/inference/misconception-v2
/v1/inference/tutor-policy
/v1/inference/learner-state
/v1/inference/evidence-reliability
```

The section now also records the service-side component set reported by `/v1/capabilities`
(5), the unchanged `Product Backend direct imports = NO` block, and the product-facing
mode of each of the five bridged components. The stale "其余 12 个" list became an
explicit 8-component list with the eligibility matrix named as its source.

**No readiness state was moved by this refresh.** `USER_VISIBLE_PREVIEW` is still exactly 1
(`student_twin`); `learner_state` is still `SHADOW_NOT_USER_VISIBLE`; `misconception_v2` is
still `SHADOW_NOT_USER_VISIBLE`; `tutor_policy` is still `SHADOW`.

Two historical blocks elsewhere in the SSOT (STEP7E / STEP7F freeze records) still say
`未接 misconception_v2 / learner_state / IRT / evidence_reliability`. Those are FROZEN
records of the state when those steps were frozen, not CURRENT claims, so they were left
untouched — editing them would falsify history.

A test enforces the new inventory:
`test_ssot_current_inventory_lists_every_real_runtime_endpoint` derives the real route set
from the service app and asserts every route appears in §49.

---

## PART B — PRIMARY TARGET: evidence_reliability

```text
EVIDENCE_RELIABILITY_COMPONENT          = REAL_DATA_PRODUCER_VARIANT_PANEL
EVIDENCE_RELIABILITY_INPUT_COMPATIBILITY= INCOMPATIBLE
EVIDENCE_RELIABILITY_REAL_EXECUTION     = YES
EVIDENCE_RELIABILITY_PRODUCT_MODE       = SHADOW_NOT_USER_VISIBLE
EVIDENCE_RELIABILITY_CONTROLS_PRODUCT_DECISION = false
EVIDENCE_RELIABILITY_WRITES_LEARNER_FACT       = false
```

### B0 — What the component actually is

`EvidenceReliabilityAdapter`, `ORIGINAL_ARCHIVE_VERIFIED`, wrapping the scientific
`ReliabilityNet` (MLP `8→16→16→1`, sigmoid) from
`runtime_src/v1/evidence_reliability/evidence_reliability.py`.

It is a **VARIANT PANEL** of five frozen checkpoints, which are FEATURE ABLATIONS with
different input dimensions — they are not interchangeable:

| variant | n_feat | features |
|---|---|---|
| `42` | 8 | all 8 (7 static + p_t) — baseline |
| `42_nort` | 7 | drop `log_rt` |
| `42_surprise` | 3 | `y`, `b_s`, `p_t` |
| `43` | 8 | baseline, seed 43 |
| `44` | 8 | baseline, seed 44 |

`variant_mode = PANEL`, `active_product_variant = null`,
`replacement_readiness = COLLECTING_DATA`. The adapter never averages, votes or
auto-selects.

**Real execution (measured, torch venv, real checkpoints):**

```text
panel latency_ms = 2.0
variant_outputs  = {42: 0.40391, 42_nort: 0.427614, 42_surprise: 0.53735,
                    43: 0.597862, 44: 0.602533}
score_range = 0.198623   score_std = 0.083664   variant_disagreement = 0.083664
determinism = True
wrong dim  -> InputValidationError: variant 42 expects 8 features, got 3
partial    -> InputValidationError: panel requires features for exactly [42, 42_nort, 42_surprise, 43, 44]
scientific_threshold = null
source_commit = WORKING_TREE(no-git-HEAD)
```

The frozen acceptance record (`PHASE1FC1_EVIDENCE_RELIABILITY_ACCEPTANCE.json`) is
`FRESH_NATIVE_PASS` with `blockers: ["standardization stats + IRT b_map not bundled"]`.

### B1 — Product semantics

```text
EVIDENCE_RELIABILITY_OUTPUT_SEMANTICS = reliability weight w in (0,1)
```

Established from the source, not from prior documentation. The training objective is a
causal learner-state update `theta <- theta + alpha * w * (y - p)` where `g(x) = w`
down-weights unreliable observations (guesses / slips) by a self-supervised
future-response LogLoss. No guess/slip label is ever used.

It is therefore **NOT** mastery, **NOT** confidence in the learner, and **NOT** a
probability of correctness. The permitted product label is:

```text
学习证据可靠度（实验）
```

The runtime's own string is pinned verbatim on both sides and a test asserts the two are
character-identical.

### B2 — User-visibility gate

The component executes, but the product cannot form its input. Decisive audit of the real
feature vector:

| feature | real semantic | product source |
|---|---|---|
| `y` | binary correctness | ✅ `learning_events.correct` (authoritative boolean) |
| `attempt_gt1` | repeat attempt | ❌ `attempt_no` is nullable, not guaranteed; invented counts forbidden |
| `has_bottom_hint` | hint used | ❌ no hint signal exists — the pipeline writes `hints = None` unconditionally |
| `hint_count` | hints used | ❌ same |
| `log_rt` | z-scored log response time | ❌ `response_time_ms` nullable, never set by backfill; invented latency forbidden |
| `log_opp` | `log1p(opportunity)` per skill | ❌ indexed by the SCIENTIFIC `skill_id` ontology; no mapping exists |
| `b_s` | IRT skill difficulty | ❌ needs the IRT `b_map`, **not bundled** (a blocker in the acceptance record itself) |
| `p_t` | running learner-state prediction | ❌ the component's OWN per-(user, skill) theta recurrence; inherits every blocker above |
| — | standardization stats | ❌ the training mean/std for the 4 z-scored continuous features are **not bundled** |

The last row is the hardest gate and was **not** in any prior document: the adapter's
`_score` receives an already-standardized vector, and the statistics that produce one were
never shipped with the checkpoints. So even with every raw field present, no caller could
scale a value into the space the checkpoints were trained on.

**No default was manufactured for any field.** Result:

```text
EVIDENCE_RELIABILITY_PRODUCT_MODE = SHADOW_NOT_USER_VISIBLE
```

with eight independent blockers, each a stable reason code:
`HINT_SIGNAL_NOT_PERSISTED`, `RESPONSE_TIME_NOT_GUARANTEED`,
`ATTEMPT_COUNT_NOT_GUARANTEED`, `SKILL_ONTOLOGY_MAPPING_ABSENT`, `IRT_B_MAP_NOT_BUNDLED`,
`STANDARDIZATION_STATS_NOT_BUNDLED`, `UPSTREAM_LEARNER_STATE_P_T_UNAVAILABLE`,
`CALIBRATION_GATE_NOT_ESTABLISHED`.

`controls_product_decision = false` and `writes_learner_fact = false` are permanent. It
annotates nothing and gates nothing.

### B3 — Runtime + product bridge

- **Runtime:** `POST /v1/inference/evidence-reliability` — typed request/response, panel
  scoring, no averaging, `422` for a malformed vector, bounded `503` when the heavy stack
  is absent (no stack trace, no 500).
- **Product:** `GET /exam/prep/scientific/evidence-reliability` — a **gated capability
  report**, following the precedent `learner_state` set in S3. `reliability_weight` is typed
  nullable and is `null` in every response this mode can produce. It reports the real model
  requirement, the real evidence window the product holds, and the exact blockers.
- Transport is `backend/science/client.py` **only**. No second HTTP client exists, and a
  test asserts the module has no `httpx` import of its own.

**Caught and fixed during verification:** `infer_panel()` computes the panel but does not
emit `score_semantics` (only single-variant `infer()` does). The first bridge
implementation read that missing key. It now pins a module constant, and a real-checkpoint
test asserts the constant is character-identical to the component's own string.

---

## PART C — MEMORY

```text
MEMORY_INPUT_COMPATIBILITY = INCOMPATIBLE
MEMORY_PRODUCT_MODE        = SHADOW_NOT_USER_VISIBLE (BLOCKED)
MEMORY_BLOCKERS            = REVIEW_RATING_HISTORY_ABSENT
                           + LAPSE_HISTORY_ABSENT
                           + INTERVAL_HISTORY_ABSENT
```

The adapter requires **seven** fields, all mandatory, no optional ones:
`delta_t`, `log_dt`, `hist_len`, `mean_interval`, `mean_rating`, `last_rating`, `lapses`.
`rating` is the **FSRS 1-4 Rating**. Output is `raw_recall_prob` plus a Platt-calibrated
`calibrated_recall_prob` (slope 7.2989, intercept -3.2013). Assets are present
(`model_state_dict.pt`, `platt_calibration.json`, `scheduler_config.json`); dependency is
`torch`; it is **not** reachable over HTTP.

Product-side reality, verified against the schema rather than assumed:

- **Review timestamps / `delta_t`** — partially derivable from `learning_events.occurred_at`
  between repeats on one item, but there is **no review event stream** (`review_completed`
  is `DEFERRED`; `review_items` was never built).
- **`hist_len`** — ABSENT. No per-item review count. `wrong_answer_states.wrong_count`
  counts wrong attempts only.
- **`mean_interval`** — ABSENT. `user_knowledge_review_settings.review_interval_days` is a
  single per-user SETTING (default 7), not interval history; `review_due_at` is one
  forward-looking timestamp.
- **`mean_rating` / `last_rating`** — ABSENT. The only self-report is
  `question_attempts.self_result`, a categorical `correct / incorrect / unknown` marker.
- **`lapses`** — ABSENT. Nothing stores FSRS "Again" history.

`NO_FABRICATED_MEMORY_RATING_LAPSE_INTERVAL = CONFIRMED` — enforced by tests that scan the
live schema (`test_memory_has_no_product_source_for_ratings_or_lapses`,
`test_the_only_self_report_is_categorical_not_a_rating`,
`test_memory_interval_setting_is_a_single_value_not_a_history`).

The existing deterministic F1C1 review interval was **NOT** replaced. No product-side
memory module exists and no runtime endpoint was added for it.

---

## PART D — IRT

```text
IRT_INPUT_COMPATIBILITY = INCOMPATIBLE
IRT_PRODUCT_MODE        = SHADOW_NOT_USER_VISIBLE (BLOCKED)
IRT_BLOCKERS            = ITEM_IDENTITY_ONTOLOGY_MISMATCH + ABILITY_STATE_ABSENT
```

Required input is `item_id`, `theta`, `correct`. `item_id` must exist in
`item_parameters.parquet` — the adapter has **no fallback** and raises
`InputValidationError` for an unknown item. The asset is keyed on **ASSISTments `skill_idx`**
(283,105 items, fit over 4,163 users); product items are `questions.id` /
`learning_events.question_id` / `practice_attempts.question_source_id`. No mapping exists,
so every real call would raise.

`theta` is ABSENT — nothing persists a per-user ability estimate.
`user_knowledge_progress.mastery_score` is a KP-level status marker, not a continuous 1PL
theta, and was not reinterpreted as one.

**A correction to a wrong assumption found during this audit:** the product DOES have
`difficulty` columns (`exam_question_bank.difficulty` = `medium` / `简单` / `中等` / `困难`;
`programming_exercises.difficulty_score` = a 0-100 editorial score). These are **editorial
categorical labels, not logit-scale IRT `b` parameters**. Substituting one would assign an
arbitrary difficulty, which is forbidden.

```text
NO_ARBITRARY_DIFFICULTY_ASSIGNED = CONFIRMED
```

The preserved semantics are the source's own: an **online 1PL-style theta update under
fixed item difficulty** — explicitly not a fitted EAP / MAP / MLE estimate, and never a
mastery score.

---

## PART E — CONCEPT_VERIFIER

```text
CONCEPT_VERIFIER_COMPATIBILITY = INCOMPATIBLE
CONCEPT_VERIFIER_PRODUCT_MODE  = SHADOW_NOT_USER_VISIBLE
CONCEPT_VERIFIER_BLOCKERS      = CONCEPT_ONTOLOGY_MISMATCH
```

Two heads, and they are not equivalent:

| capability | historical support | AUROC | verdict |
|---|---|---|---|
| `concept_alignment` | SUPPORTED | 0.828 ± 0.011 | shadow candidate |
| `answer_consistency` | NOT_SUPPORTED | 0.5022 (≈ random) | needs model replacement |

Inputs are `question` (**English, Eedi-style**), `concept`, `answer`. The product's
questions are Chinese CS408 text, and `concept` has no product counterpart at all — CS408
knowledge points have no mapping onto English Eedi constructs. `answer` exists but feeds
only the head that is not supported.

`verification_score` is `softmax(logits)[:,1]` with `scientific_threshold: null`; the
derived 0.5 is explicitly `ENGINEERING_DEFAULT` and `label_is_engineering_derived: true`.

**The candidate use in the brief — verifying question↔concept association — does not
survive the ontology check**, so it was reported and stopped.

```text
CONCEPT_VERIFIER_AUTHORITY = NOT ADVISORY, NOT ACTIVE
```

No product module, no runtime endpoint, no path by which it could overwrite canonical
ontology. A test asserts it is never `PREVIEW`.

---

## PART F — LEARNER_STATE FROZEN BLOCK

```text
LEARNER_STATE_PRODUCT_MODE = SHADOW_NOT_USER_VISIBLE
```

Frozen. No further CS408 mapping was attempted — the S3 finding stands and was re-asserted
rather than re-litigated. Blockers remain independent:

```text
ONTOLOGY_MAPPING_ABSENT
CALIBRATION_GATE_NOT_ESTABLISHED
```

`torch` was **not** installed into the serving venv (or any venv) for `learner_state`. Its
real-model validation already passed and is untouched. The endpoint's gated report still
produces no `next_response_probability`.

---

## PART G — MISCONCEPTION / TUTOR POLICY

```text
MISCONCEPTION_PRODUCT_MODE = SHADOW_NOT_USER_VISIBLE   (unchanged)
TUTOR_POLICY_PRODUCT_MODE  = SHADOW                    (unchanged)
```

Neither was promoted merely because a dependency could be installed. `misconception_v2`
keeps its independent Eedi/English ontology mismatch; `tutor_policy` keeps its independent
missing truthful turn-state fields and still answers `available: false` rather than
fabricating a turn. Both bridges are preserved exactly as S1/S2 left them.

---

## PART H — SHARED SCIENTIFIC PRODUCT CONTRACT

Every product-facing scientific response carries the shared authority block, unchanged in
shape and now including the two new surfaces:

```text
component, mode, controls_product_decision, writes_learner_fact, generated_at,
request_id, runtime_release_id, source_class, latency_ms, blockers, semantics
```

`controls_product_decision` and `writes_learner_fact` are `false` for every component, and
a parametrised test asserts this across all five scientific routes.

```text
NO_SCIENTIFIC_PREVIEW_SILENTLY_BECOMES_PRODUCT_TRUTH = CONFIRMED
```

The block is **required** by the response models — a test asserts
`EvidenceReliabilityPreviewResponse.model_fields["metadata"].is_required()`.

---

## PART I — SCIENTIFIC CAPABILITY SUMMARY

```text
SCIENTIFIC_CAPABILITIES_ENDPOINT = GET /exam/prep/scientific/capabilities
```

Typed, authenticated (401 anonymously), read-only, and it calls no runtime. It reports
**product-facing readiness**, not endpoint existence — `available` is documented in the
payload itself as "the product can produce this component's output from real facts it holds
today — NOT the mere existence of a runtime endpoint".

```text
totals: components = 13 | available = 2 | user_visible = 1
        controls_product_decision = 0 | writes_learner_fact = 0
```

| component | mode | available | user_visible |
|---|---|---|---|
| `student_twin` | PREVIEW | ✅ | ✅ |
| `misconception_v2` | SHADOW_NOT_USER_VISIBLE | ✅ | ❌ |
| `learner_state` | SHADOW_NOT_USER_VISIBLE | ❌ | ❌ |
| `tutor_policy` | SHADOW | ❌ | ❌ |
| `evidence_reliability` | SHADOW_NOT_USER_VISIBLE | ❌ | ❌ |
| `memory` | SHADOW_NOT_USER_VISIBLE | ❌ | ❌ |
| `irt` | SHADOW_NOT_USER_VISIBLE | ❌ | ❌ |
| `concept_verifier` | SHADOW_NOT_USER_VISIBLE | ❌ | ❌ |
| `difficulty_prior` / `planner` / `tutor_guard` / `execution_router` / `domestic_registry` | UNAVAILABLE | ❌ | ❌ |

Note the deliberate asymmetry: `learner_state` and `evidence_reliability` **have** runtime
endpoints yet are reported `available: false`, because the product cannot feed them. That
is the whole point of the endpoint.

No filesystem path, asset location or stack trace is exposed — asserted by a test that
scans the raw response text for `D:\`, `C:\`, `ZhixueAI`, `model_assets`, `runtime_src`
and `Traceback`.

---

## PART J — DATA-PLANE PRODUCTION MIGRATION READINESS

```text
REAL_DB_COPY_MIGRATION_TO_HEAD = PASS
```

Run on a **byte-for-byte copy** (`SHA256` verified identical before use). The real file was
opened read-only and never written.

The real database is a **72-table legacy** database that predates Alembic entirely: it has
**no `alembic_version` table at all**, and none of `learning_events`, `model_predictions`,
`model_inference_runs`.

| check | result |
|---|---|
| `alembic upgrade head` | 0001 → 0009 applied cleanly, 0 errors |
| `alembic_version` | `20260919_0009` |
| tables | 71 → **85** (+14), **0 dropped** |
| `PRAGMA integrity_check` | `ok` |
| `PRAGMA foreign_key_check` | clean |
| pre-existing row counts | **every table unchanged** |

New tables: `ai_cost_records`, `ai_requests`, `alembic_version`, `exam_prep_profiles`,
`learning_events`, `model_inference_runs`, `model_predictions`, `model_versions`,
`practice_attempts`, `practice_sessions`, `subscriptions`, `usage_budgets`, `usage_ledger`,
`wrong_answer_states`.

Protected content preserved exactly: `exam_question_bank = 9333`,
`programming_exercises = 1923`, `knowledge_points = 32`. Membership tables
(`user_service_memberships`, `membership_orders`, `membership_grants`, `redemption_codes`)
and exam/wrong-answer legacy tables are untouched.

**Application starts without a `create_all` dependency:**

```text
create_all invoked = True
tables created by import = []      # ZERO
```

`Base.metadata.create_all` was replaced with a hard no-op before importing `main`. The app
started, served every route, and created **no** table — the schema at HEAD comes entirely
from Alembic.

### J1 — BACKFILL

```text
BACKFILL_EVENTS_CREATED = 0
BACKFILL_EVENTS_SKIPPED = 0
BACKFILL_IDEMPOTENT     = YES
```

**Nothing was fabricated, because nothing was reconstructable.** The real database is
content-only: it contains **0 users and 0 attempts across all five backfill sources**
(`ai_question_attempts`, `question_attempts`, `exam_practice_attempts`,
`past_paper_attempts`, `programming_exercise_progress`). The backfill ran cleanly against
the migrated schema, mirrored 0 rows, failed 0, and a second run added 0 more.

The classification matrix it reports is real and complete — 5 `PARTIAL` sources with their
exact missing fields, and 2 `INELIGIBLE` sources with reasons:

```text
programming_exercise_submissions  INELIGIBLE  duplicate of programming_exercise_progress;
                                              mirroring both would double-count one submission
code_challenge_attempts           INELIGIBLE  status is keyword-matched from AI prose, not an
                                              execution result — using it would fabricate a verdict
```

### J2 — USER-VISIBLE READINESS

```text
POST_MIGRATION_RECORDS_API    = PASS   GET /exam/prep/records -> 200
POST_MIGRATION_STUDENT_TWIN   = PASS   GET /exam/prep/scientific/student-twin -> 200
```

Core record reads needed no runtime. With one real CS408 event written through the real
product path, Student Twin returned:

```text
mode = PREVIEW
input_summary.event_count = 1
runtime_release_id = zhixue-runtime-v1-phase1gr-p1
state keys = ability_uncertainty, active_course, concepts, exam_date, global_ability,
             learning_goal, model_versions, recent_activity_summary, state_generated_at,
             time_budget, user_id
```

That is the **full chain**: migrated database → product API → a REAL Scientific Runtime
Service on a free port → a real deterministic state. Every check above ran in subprocesses
with their own `DATABASE_URL`, so none of it depended on this session's process state.

---

## PART K — HEAVY IMPORT BOUNDARY

```text
PRODUCT_BACKEND_HEAVY_IMPORTS = ZERO
```

`torch`, `transformers`, `faiss`, `sklearn`, `sentence_transformers` and `zhixue_runtime`
are all absent from `sys.modules` in the backend process, and no new module imports them.
`backend/science/client.py` remains the only transport.

The venv split was re-measured and is unchanged: the torch venv cannot serve HTTP (no
pydantic) and the serving venv cannot run the heavy components (no torch). The new
real-checkpoint test therefore lives in the runtime environment and **skips** rather than
fails elsewhere — which is why the semantics constant is pinned by reading the bridge
source instead of importing it there.

---

## PART L — FAILURE ISOLATION

```text
SCIENTIFIC_FAILURE_ISOLATED = YES
```

With the scientific client replaced by a dead transport, every one of these returned
**200**, none returned 500:

```text
/exam/prep/records
/exam/prep/scientific/student-twin
/exam/prep/scientific/learner-state
/exam/prep/scientific/evidence-reliability
/exam/prep/scientific/capabilities
/exam/prep/catalog
/wrong-answers
```

`/exam/prep/scientific/evidence-reliability?probe_runtime=true` under outage answers
`runtime_reachable: false`, `reliability_weight: null`, mode unchanged. The capability
summary needs no runtime at all. Knowledge, Practice, Past Papers, Wrong, Plan and Records
are unaffected.

---

## PART M — TESTS

All 21 required groups are covered:

| # | requirement | where |
|---|---|---|
| 1 | SSOT endpoint inventory current | `test_ssot_current_inventory_lists_every_real_runtime_endpoint` |
| 2 | evidence_reliability real input audit | `test_evidence_reliability_input_audit_matches_the_real_component` |
| 3 | real runtime execution if eligible | `test_panel_executes_deterministically_and_returns_real_weights` (+8) |
| 4 | no learner-state mutation | `test_evidence_reliability_writes_no_learner_fact` |
| 5 | memory exact-input gate | `test_memory_requires_an_interval_rating_and_a_lapse_history` |
| 6 | no fabricated memory rating/lapse/interval | `test_memory_has_no_product_source_for_ratings_or_lapses` (+2) |
| 7 | IRT exact-input gate | `test_irt_requires_a_scientific_item_identity_and_an_ability_state` |
| 8 | no arbitrary difficulty | `test_irt_assigns_no_arbitrary_difficulty` |
| 9 | concept_verifier gate | `test_concept_verifier_has_no_cs408_concept_space` |
| 10 | scientific capability summary | `test_capability_summary_reports_product_readiness_not_endpoint_existence` (+3) |
| 11 | authority metadata | `test_every_scientific_response_carries_the_authority_block` (+1) |
| 12 | cross-user isolation | `test_evidence_reliability_is_scoped_to_the_caller` |
| 13 | outage isolation | `test_core_exam_flows_survive_a_scientific_outage` (+2) |
| 14 | heavy imports zero | `test_product_backend_heavy_imports_are_zero` (+1) |
| 15 | migration real-DB-copy → HEAD | `test_real_db_copy_reaches_head_with_integrity_ok` |
| 16 | protected row preservation | `test_no_table_was_dropped_and_every_legacy_row_survived` (+1) |
| 17 | historical record backfill | `test_backfill_reconstructs_only_what_is_reconstructable` |
| 18 | backfill idempotency | `test_backfill_is_idempotent` |
| 19 | records work after migration | `test_records_api_works_against_the_migrated_schema` |
| 20 | Student Twin vs migrated data plane | `test_student_twin_reaches_the_real_runtime_for_a_real_event` |
| 21 | OpenAPI concrete | `test_openapi_is_concrete_for_every_new_endpoint` (+1) |

```text
TARGETED_TESTS = 47 passed / 0 failed
   test_s4_scientific_productization.py    34 passed
   test_s4_migration_readiness.py          13 passed (0 skipped — the real runtime started)

RUNTIME_TESTS = 41 passed / 0 failed / 2 skipped
   scientific_runtime_service/tests        31 passed / 2 skipped   (runtime-service venv)
   test_evidence_reliability_real_model.py 10 passed                (torch venv, real checkpoints)
```

---

## PART N — OPENAPI

`frontend/src/types/api.ts` was regenerated with the project's own tooling
(`openapi-typescript 7.13.0`, the version `api:generate` resolves), against a spec served
by a standalone uvicorn on **port 8947** (never 8000) bound to an explicit **TEMP
`DATABASE_URL`** copy of the real database. `package.json` was not modified and the file
was not hand-edited — it retains its auto-generated header.

```text
paths before = 328   after = 330
ADDED   (2): /exam/prep/scientific/capabilities
             /exam/prep/scientific/evidence-reliability
REMOVED (0)
```

No unrelated drift. All five new schemas are present and concrete
(`EvidenceReliabilityPreviewResponse`, `EvidenceReliabilityRequirement`,
`ScientificCapabilitiesResponse`, `ScientificCapabilityEntry`,
`ScientificCapabilityTotals`).

---

## PART O — REGRESSION

```text
FULL_BACKEND_TESTS   = 1304 passed / 0 failed  (897.80s)
RUNTIME_TESTS        = 41 passed / 0 failed / 2 skipped
FRONTEND_TYPECHECK   = PASS
FRONTEND_LINT        = PASS
FRONTEND_UNIT_TESTS  = 82 passed (24 files)
FRONTEND_BUILD       = PASS
```

One pre-existing runtime-service test was updated because it pinned the exact component
tuple: `test_capabilities` now expects the 5-component list. This is a deliberate contract
update, not a weakening — the test additionally now asserts `runtime_release_id` is
unchanged, since serving an extra component changes no scientific computation.

`RUNTIME_RELEASE_ID` was **not** bumped: the release id is frozen provenance written onto
every `ModelPrediction` row and naming a preservation-critical deploy artifact. Adding an
HTTP capability changes no scientific computation, so the new capability set is reported
through `/v1/capabilities` instead.

---

## PART P — REAL DB SAFETY

```text
REAL_APP_DB_MUTATED = NO
```

| property | before | after |
|---|---|---|
| SHA256 | `1c1b2d8538d7a3c52a79a64dec904c69c6ec964b86decbc6508d0d2a438fe522` | identical |
| size | 64,917,504 | identical |
| mtime | 2026-09-16 21:24:23 | identical |
| table count | 72 | 72 |
| `integrity_check` | `ok` | `ok` |
| `learning_events` | absent | **still absent** |
| `alembic_version` | absent | **still absent** |
| content rows | 9333 / 1923 / 32 | identical |

The real database was never migrated as a side effect, never written, and never opened
read-write. Two tests assert this directly (`test_the_real_database_was_never_modified`,
`test_the_real_database_still_has_its_legacy_shape`).

```text
SCIENTIFIC_REQUIRED_REQUEST_UNKNOWN  = 0
SCIENTIFIC_REQUIRED_SUCCESS_UNKNOWN  = 0
```

Every scientific request the sprint issues has a known, asserted outcome. No test asserts
on a shape it did not verify, and no gate is claimed from an assumption.

---

## PART Q — FINAL RESPONSE

```text
ACCEL_SPRINT_S4_COMPLETE

SSOT_SCIENTIFIC_RUNTIME_CURRENT_UPDATED = YES

EVIDENCE_RELIABILITY_COMPONENT = REAL_DATA_PRODUCER_VARIANT_PANEL
EVIDENCE_RELIABILITY_INPUT_COMPATIBILITY = INCOMPATIBLE
EVIDENCE_RELIABILITY_REAL_EXECUTION = YES
EVIDENCE_RELIABILITY_PRODUCT_MODE = SHADOW_NOT_USER_VISIBLE
EVIDENCE_RELIABILITY_OUTPUT_SEMANTICS = reliability weight w in (0,1)
EVIDENCE_RELIABILITY_CONTROLS_PRODUCT_DECISION = false
EVIDENCE_RELIABILITY_WRITES_LEARNER_FACT = false

MEMORY_INPUT_COMPATIBILITY = INCOMPATIBLE
MEMORY_PRODUCT_MODE = SHADOW_NOT_USER_VISIBLE
MEMORY_BLOCKERS = REVIEW_RATING_HISTORY_ABSENT + LAPSE_HISTORY_ABSENT + INTERVAL_HISTORY_ABSENT

IRT_INPUT_COMPATIBILITY = INCOMPATIBLE
IRT_PRODUCT_MODE = SHADOW_NOT_USER_VISIBLE
IRT_BLOCKERS = ITEM_IDENTITY_ONTOLOGY_MISMATCH + ABILITY_STATE_ABSENT

CONCEPT_VERIFIER_COMPATIBILITY = INCOMPATIBLE
CONCEPT_VERIFIER_PRODUCT_MODE = SHADOW_NOT_USER_VISIBLE
CONCEPT_VERIFIER_BLOCKERS = CONCEPT_ONTOLOGY_MISMATCH

LEARNER_STATE_PRODUCT_MODE = SHADOW_NOT_USER_VISIBLE
MISCONCEPTION_PRODUCT_MODE = SHADOW_NOT_USER_VISIBLE
TUTOR_POLICY_PRODUCT_MODE = SHADOW

SCIENTIFIC_CAPABILITIES_ENDPOINT = GET /exam/prep/scientific/capabilities

REAL_DB_COPY_MIGRATION_TO_HEAD = PASS
BACKFILL_EVENTS_CREATED = 0
BACKFILL_EVENTS_SKIPPED = 0
BACKFILL_IDEMPOTENT = YES

POST_MIGRATION_RECORDS_API = PASS
POST_MIGRATION_STUDENT_TWIN = PASS

PRODUCT_BACKEND_HEAVY_IMPORTS = ZERO
SCIENTIFIC_FAILURE_ISOLATED = YES

SCIENTIFIC_REQUIRED_REQUEST_UNKNOWN = 0
SCIENTIFIC_REQUIRED_SUCCESS_UNKNOWN = 0

TARGETED_TESTS = 47 passed / 0 failed
RUNTIME_TESTS = 41 passed / 0 failed / 2 skipped
FULL_BACKEND_TESTS = 1304 passed / 0 failed

FRONTEND_TYPECHECK = PASS
FRONTEND_LINT = PASS
FRONTEND_UNIT_TESTS = 82 passed
FRONTEND_BUILD = PASS

REAL_APP_DB_MUTATED = NO

NEXT_USER_VISIBLE_COMPONENTS = NONE
BLOCKERS = evidence_reliability: HINT_SIGNAL_NOT_PERSISTED, RESPONSE_TIME_NOT_GUARANTEED,
           ATTEMPT_COUNT_NOT_GUARANTEED, SKILL_ONTOLOGY_MAPPING_ABSENT, IRT_B_MAP_NOT_BUNDLED,
           STANDARDIZATION_STATS_NOT_BUNDLED, UPSTREAM_LEARNER_STATE_P_T_UNAVAILABLE,
           CALIBRATION_GATE_NOT_ESTABLISHED
           memory: REVIEW_RATING_HISTORY_ABSENT, LAPSE_HISTORY_ABSENT, INTERVAL_HISTORY_ABSENT
           irt: ITEM_IDENTITY_ONTOLOGY_MISMATCH, ABILITY_STATE_ABSENT
           concept_verifier: CONCEPT_ONTOLOGY_MISMATCH
           learner_state: ONTOLOGY_MAPPING_ABSENT, CALIBRATION_GATE_NOT_ESTABLISHED
           misconception_v2: ONTOLOGY_MISMATCH (Eedi/English)
           tutor_policy: MISSING_TRUTHFUL_TURN_STATE_FIELDS
```

---

## WHAT WOULD UNBLOCK WHAT

For a future sprint, stated honestly rather than as a plan:

**evidence_reliability** is the closest of the four blocked components, because it is the
only one whose blocker is *data collection* rather than an ontology gap. It needs the
product to start persisting a hint signal, a guaranteed response time, and a guaranteed
attempt count — all of which are product decisions, not scientific ones. Even then it would
still need the missing `b_map`, the standardization statistics, and a CS408→skill mapping.
Do not treat "we now log hints" as sufficient; it removes 3 of 8 blockers.

**memory** needs a genuinely new collection surface — a review event stream carrying an
FSRS rating — which does not exist in any form today. Cheaper and more honest to keep the
deterministic F1C1 interval than to approximate a rating.

**irt** cannot be unblocked by data collection at all, because the blocker is item identity:
the asset is keyed on a scientific ontology the product does not share.

**concept_verifier** is blocked on language and concept space, not on data volume.
