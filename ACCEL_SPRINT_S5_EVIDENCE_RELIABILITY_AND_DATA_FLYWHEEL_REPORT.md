# ACCEL_SPRINT_S5 — EVIDENCE_RELIABILITY MODEL ACTIVATION + PRODUCT-NATIVE SCIENTIFIC DATA FLYWHEEL V1

**Verdict: COMPLETE.**

```text
EVIDENCE_RELIABILITY_PRODUCT_MODE = SHADOW_NOT_USER_VISIBLE
FIRST_UNSATISFIED_GATE             = PART A1 SCALER RECOVERY (reconstruction did not verify)
```

The sprint's premise was conditional: promote `evidence_reliability` to
`USER_VISIBLE_PREVIEW` **if** its original preprocessing could be reconstructed exactly. It
could not be — and the failure is a MEASUREMENT, not a search that ran out of road. What
the sprint did deliver is the exact input contract, the factual attempt telemetry, the
CS408-native concept schema and the offline KT dataset contract that a future native model
will be trained from.

`REAL_APP_DB_MUTATED = NO`. No frontend UI was implemented.

---

## 0. FILES CHANGED

| File | Change |
|---|---|
| `backend/science/evidence_reliability.py` | exact code-derived feature schema; per-feature product classification; scaler gate with recorded evidence; mode derived from the gate |
| `backend/science/kt_dataset.py` | **new** — offline deterministic KT dataset export + audit |
| `backend/science/capabilities.py` | four independent readiness dimensions per component |
| `backend/science/contract.py` | `ScalerGate`, `KtDatasetAuditResponse`, extended requirement model |
| `backend/learning/practice/telemetry.py` | **new** — the one canonical attempt/evidence envelope |
| `backend/learning/practice/models.py` | `response_time_source`, `attempt_index` |
| `backend/learning/practice/service.py` | `record_attempt(telemetry=…)` |
| `backend/learning/practice/events.py` | telemetry provenance carried onto the event |
| `backend/learning/records/native_concept.py` | **new** — the CS408-native concept reference |
| `backend/learning/records/envelope.py` | delegates the concept key set to `native_concept` |
| `backend/data_plane/models.py` | `response_time_source`, `attempt_index` on `learning_events` |
| `backend/routers/practice.py` | typed telemetry payload at the HTTP boundary |
| `backend/routers/exam_prep.py` | `GET /exam/prep/scientific/kt-dataset-audit` |
| `backend/science/tutor_policy.py` | PART M pedagogical-action ledger audit |
| `migrations/versions/20260919_0010_attempt_telemetry_provenance.py` | **new** — one additive migration |
| `scripts/reconstruct_evidence_reliability_scaler.py` | **new** — deterministic re-derivation tool |
| `scripts/verify_evidence_reliability_frozen_reproduction.py` | **new** — the decisive check |
| `backend/tests/test_s5_evidence_reliability_and_flywheel.py` | **new** — 72 tests |
| `scientific_runtime_service/tests/test_evidence_reliability_scaler.py` | **new** — 9 tests, torch env |
| `frontend/src/types/api.ts` | regenerated (no hand edits) |
| 4 test files | pinned `EXPECTED_HEAD` advanced to `20260919_0010`; two BC8 "no migration was needed" assertions restated as chain properties |

---

## PART A — THE SCALER GATE

### A0. What was recovered

The authoritative research archive (outside the repo) contains the complete frozen
`evidence_reliability` project. Extracted and digest-verified:

```text
data/splits/cohort.parquet                     259,399 rows / 4,163 users / 145 skills
data/splits/split_{42,43,44}.parquet           user-disjoint 70/15/15
results/irt_skill_params.json                  supplies b_1pl
results/comparison_{42,43,44}.json             supplies alpha = 1.0
results/reliability_predictions_*.parquet      per-row (y, p_base, p_rel, w_rel)
checkpoints/reliability_net_{42,42_nort,42_surprise,43,44}.pt
src/{models,data,evaluation,baselines,utils}/   byte-identical to the recovered copy
```

All five checkpoint sha256 match the frozen `artifact.json` exactly. The cohort matches the
frozen provenance report exactly. The source files match the recovered copy byte for byte.

### A1/A2. The reconstruction does not verify

No fitted scaler artifact exists anywhere. The pipeline's rule IS recoverable —
train-frame `mean`/`std` over `log_rt, hint_count, log_opp, b_s`, `(v−μ)/σ`, sample std — so
it was re-derived from the frozen artifacts and then CHECKED against the experiment's own
recorded per-row output:

```text
p_base (features irrelevant: alpha + y + sequence layout)   max |delta| = 1.19e-07  EXACT
y ordering and values                                                              IDENTICAL
weights, sequences whose first response was CORRECT                             EXACT
weights, sequences whose first response was INCORRECT       mean |delta| = 0.047   DIVERGES (31%)
```

A free numerical fit over all four `(mean, std)` pairs **does** reproduce the frozen weights
(rmse 9.3e-05), which proves the frozen numbers really are `g(x)` for some standardizer.
Three of its four pairs land within 0.1% of the re-derivation. The fourth — `b_s` — does
not: the frozen run needs a skill-difficulty column whose statistics the archived
`irt_skill_params.json` does not produce, under any mapping the source contains.

**Conclusion: a required input is absent from the archive.** Following the pipeline gives a
standardizer that is deterministic but UNVERIFIED, and an unverified standardizer is
precisely what the gate exists to refuse. Neither half of PART A1 holds.

Per PART A2 the promotion path stops here. The product mode is **derived** from the gate
(`production_mode()`), so the two cannot drift apart, and the evidence is carried as data
(`SCALER_RECOVERY_EVIDENCE`) rather than prose so it cannot be quietly softened.

### A3. Status

```text
EVIDENCE_RELIABILITY_SCALER      = NOT_RECOVERED
SCALER_RECOVERY_METHOD           = NOT_RECOVERED  (attempted: RECONSTRUCTED_FROM_FROZEN_DATA)
SCALER_PROVENANCE                = checkpoints verified against model_assets/artifact.json;
                                   cohort/split/IRT/alpha recovered and digest-pinned;
                                   b_s column used at training time NOT recoverable
```

---

## PART B — REAL MODEL VALIDATION

All five checkpoints load with their frozen dimensions (`8 / 7 / 3 / 8 / 8`), execute
deterministically, and return weights in `(0,1)`; the panel never averages, votes or
auto-selects. The real transform was exercised end to end (`test_the_panel_executes_on_a_real_standardized_vector`).
No formula is duplicated in the Product Backend — the product module holds a schema, a
classification and a gate, and computes nothing.

---

## PARTS C/D — THE EXACT CONTRACT AND THE TELEMETRY

The feature vector, read off the frozen source rather than remembered:

```text
x = [ y, attempt_gt1, has_bottom_hint, z(log_rt), z(hint_count), z(log_opp), z(b_s), p_t ]
     \_________________ raw 0/1 ______________/  \_________ z-scored ________/
```

`log_rt` = `log1p(max(ms,0))`; `log_opp` = `log1p(opportunity)`; `b_s` = `skill_id → b_map`
with `fillna(0.0)` BEFORE standardization; `p_t` = `sigmoid(theta_t)`, concatenated last and
NOT z-scored. Variant widths are strict subsets of this order.

```text
y                       AVAILABLE_NOW
attempt_gt1              CAN_BE_COLLECTED_FACTUALLY
log_rt                   CAN_BE_COLLECTED_FACTUALLY
has_bottom_hint          NOT_AVAILABLE
hint_count               NOT_AVAILABLE
log_opp                  SEMANTICALLY_INCOMPATIBLE
b_s                      SEMANTICALLY_INCOMPATIBLE
p_t                      SEMANTICALLY_INCOMPATIBLE
PRODUCT_FEATURE_COMPATIBILITY = INCOMPATIBLE
```

**Telemetry (`learning.practice.telemetry`) — one envelope, three rules.**

- **Timing.** A duration is admitted only with a declared source, and each source names its
  start boundary, submit boundary, unit and background-tab behaviour. `UNAVAILABLE` may not
  carry a number, and a source may not omit one. `created_at − submitted_at` and session
  spans are named forbidden and are not performed anywhere.
- **Hints.** `NO_HINT_MECHANISM` is its own value and admits **no** count. Storing `0` there
  would assert an observation that was never made. A real counted zero is still allowed.
- **Attempt index.** 1-based ordinal over canonical `(user_id, question identity)` — not a
  session position and not the past-paper sitting number, which keeps its own column.
- **Difficulty.** `简单 / 中等 / 困难` is never converted to `−1/0/+1`, to an IRT `b`, or to a
  continuous difficulty; a guard refuses a numeric encoding outright.

Telemetry provenance is deliberately NOT part of the graded-fact digest: adding it would
change the hash of unchanged facts and make a legitimate replay raise `AttemptConflict`
against history.

---

## PART E — NO BACKFILL

The migration adds no server default and executes no `UPDATE`. Every existing row keeps NULL
in all four columns because the boundary, the count and the provenance were not observed
when the row was written. `PRAGMA integrity_check` on the migrated copy returns `ok`.

---

## PARTS F/G/I/J — WHY THE SURFACE STAYS CLOSED

PART F requires the preprocessing gate AND product input compatibility. The first fails
(PART A). The second would fail independently: two features are `NOT_AVAILABLE` (no hint
system exists on any CS408 surface) and three are `SEMANTICALLY_INCOMPATIBLE` (they are
indexed by the scientific skill ontology). PART J adds a third reason: the frozen record
carries `scientific_threshold = null`, so no calibration was ever established.

```text
controls_product_decision = false        writes_learner_fact = false
```

The output may not change grading, knowledge status, wrong-answer status, Student Twin,
plan, question selection, model routing or a tutor response — and it does not, because no
output is produced.

---

## PART K — CS408-NATIVE CONCEPT REFERENCE

Exam identity and concept identity are separate spaces. `exam_track_id` is **never**
recorded on a fact (a track is the learner's bundle choice, not an attribute of what
happened), and `exam_subject_id` is exam identity, not a concept — a subject-only fact
yields **no** concept key rather than `"cs_408"` dressed up as one.

```text
chapter practice   exam_module_id + knowledge_point_id
past papers        exam_module_id ONLY — correct granularity, not a gap
programming        programming_language + exercise_id
```

No concept link is ever derived from a title, a path, a name or a question number.

---

## PART L — FUTURE KT DATASET CONTRACT

`science.kt_dataset` is an offline deterministic export over canonical events:
`(learner_ref, concept_key) → ordered interactions` carrying `attempt_ref`, `item_ref`,
an authoritative boolean `correct`, `occurred_at`, and S5 telemetry where observed.
Ordering is `(occurred_at, event_id)`; `dataset_hash` is a sha256 over the canonical body,
so an export is auditable by re-running it. Tri-state is preserved — an unanswered or
ungraded item is EXCLUDED and COUNTED, never read as wrong.

No learner name, username or email; `learner_ref` is a fixed-domain digest. No question
stem, answer, explanation, source code, prompt or AI response. It trains nothing.

The observable surface is `GET /exam/prep/scientific/kt-dataset-audit`, which reports
contract health and carries no rows.

---

## PART M — TUTOR DATA FLYWHEEL

```text
PEDAGOGICAL_ACTION_LEDGER_READY = NO
```

The orchestrator composes `permission → router → estimate → reserve → gateway → settle`.
Every choice it makes is about HOW TO CALL A MODEL. It chooses no action in the frozen
`focus / generic / probing / telling` ontology. `prompts.detect_question_type` derives a
response STRUCTURE — a property of what the learner asked for, not a tutor decision — and it
is not persisted, so there is no history either. No ledger is invented; a fabricated
`prev_actions` column would fabricate the dominant input signal of the model it would train.

---

## PART N — CAPABILITY SUMMARY

Each component now reports four independent dimensions — `runtime_available`,
`scientifically_compatible`, `product_input_ready`, `user_visible` — plus `mode` and
`blockers`, with a guard that the reachable set matches the served set.

```text
student_twin           rt=T sci=T in=T vis=T PREVIEW
learner_state          rt=T sci=F in=F vis=F SHADOW_NOT_USER_VISIBLE
misconception_v2       rt=T sci=F in=T vis=F SHADOW_NOT_USER_VISIBLE
tutor_policy           rt=T sci=T in=F vis=F SHADOW
evidence_reliability   rt=T sci=F in=F vis=F SHADOW_NOT_USER_VISIBLE
(memory / irt / concept_verifier / difficulty_prior / planner / tutor_guard /
 execution_router / domestic_registry)  rt=F sci=F in=F vis=F
totals: components=13 available=2 user_visible=1
```

Endpoint existence never implies readiness: five components are reachable and four of them
are not usable.

---

## PART O — MIGRATION

One additive migration, `20260919_0010`, adding four nullable columns across
`practice_attempts` and `learning_events`. Validated on a **byte-for-byte COPY** of the real
`backend/app.db`: upgrade reaches head, `PRAGMA integrity_check` returns `ok`, the new
columns arrive EMPTY (nothing backfilled), and the protected content's row counts are
unchanged. The real database was never opened for writing and its digest is asserted
unchanged before and after.

---

## PART O.1 — DEPLOYMENT CONSEQUENCE (READ THIS BEFORE RELEASING)

`MIGRATION_ADDED = YES`, and the new columns are **required** for the code to run against an
existing database: `learning_events` and `practice_attempts` both gain
`response_time_source` / `attempt_index`, and SQLAlchemy will select them. `create_all` does
NOT add columns to tables that already exist, so a deployment that skips the migration will
fail rather than degrade.

```text
MIGRATION_HEAD 20260919_0010
```

The real `backend/app.db` has NOT been migrated by this sprint (it is at an earlier head
and is never touched directly — mtime unchanged at 2026-09-16 21:24). Releasing this code
to any environment requires the normal deployment path to run `alembic upgrade head` there.

---

## PART P/R — TESTS AND REGRESSION

```text
targeted S5 (backend)                        72 passed
runtime scaler / scaler-recovery              9 passed   (D:/ZhixueAI/envs/runtime)
runtime real-model (ER panel, learner_state) 17 passed   (D:/ZhixueAI/envs/runtime)
runtime service API + import closure         31 passed   (D:/ZhixueAI/envs/runtime-service)
FULL BACKEND                              1376 passed / 0 failed   (547s)
frontend typecheck / lint / unit / build   PASS / PASS / 82 passed / PASS
```

Four pre-existing tests pinning the migration head were advanced to `20260919_0010`, and two
BC8/BC8R1 "this sprint added no migration" assertions were restated as properties of the
revision chain rather than of the head — so that a later sprint advancing the head is not
misread as BC8 having needed a migration.

---

## PART S — FINAL CLASSIFICATION

```text
EVIDENCE_RELIABILITY_PRODUCT_MODE = SHADOW_NOT_USER_VISIBLE
```

Not halfway: the gate is open, the exact first unsatisfied gate is PART A1 (scaler
recovery), and the promotion path for this component is stopped there while the data-flywheel
work continues.
