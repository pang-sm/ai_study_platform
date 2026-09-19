# ACCEL_SPRINT_S2 — StudentTwin CS408 Productization Gate Closure + SSOT Governance Update

Date: 2026-09-19. Repository: `C:\Users\26477\Desktop\ai_study_platform`.
Mode: narrow productization closure. **No frontend UI was implemented.**

```text
ACCEL_SPRINT_S2_COMPLETE
```

Baseline: ACCEL_SPRINT_S1 = COMPLETE, full backend 1211 passed / 0 failed.

---

## 1. The decision, and what it does not touch

The Productization Gate is **approved** by explicit product decision: CS408 factual
`question_answered` events **MAY** be StudentTwin eligible when, and only when, they carry
an authoritative binary correctness fact.

This is an **input-domain** decision. Nothing scientific moved:

```text
RUNTIME_RELEASE_ID_CHANGED = NO
StudentTwin formula           unchanged
state-transition rules        unchanged
scientific model assets       unchanged
```

`question_answered` is **not** renamed to `course_practice`. They remain two families with
two owners and two event types.

---

## 2. The eligibility rule — one rule, two consumers

The rule lives in `backend/data_plane/eligibility.py`
(`student_twin_input_eligibility`), as a pure predicate over three facts. It never touches
the database, a session, or a model.

```text
eligible  ⟺  family permits it            (course_practice | question_answered)
          AND user_answer is non-empty
          AND correct is exactly true/false
          AND judge is not self_review
```

"Eligible" means **authoritative binary correctness**: a real machine verdict on a real
submission.

### The rule never reads `score`

This is not a stylistic choice — it is the correction the gate names explicitly. A score is
not a correctness verdict:

* an **AI-graded past-paper item** can carry a real authoritative score with `correct`
  still `null`;
* an **unanswered item** can carry a legacy `score: 0` (the exact defect S1 closed at the
  record boundary).

Deriving correctness from a score would make both of those eligible. A test asserts the
rule has no `score` parameter at all, so it is structurally incapable of doing so.

### Case table (each row is a passing test)

| case | verdict | reason code |
| --- | --- | --- |
| CS408 answered choice, `correct: true` | **ELIGIBLE** | `AUTHORITATIVE_BINARY_CORRECTNESS` |
| CS408 answered choice, `correct: false` | **ELIGIBLE** | `AUTHORITATIVE_BINARY_CORRECTNESS` |
| blank answer (`user_answer = ""`) | not eligible | `NO_USER_ANSWER` |
| `judge = self_review` | not eligible | `JUDGE_NOT_AUTHORITATIVE` |
| `correct = null` (AI-graded, real score) | not eligible | `CORRECTNESS_NOT_BINARY` |
| any `score` value with `correct = null` | not eligible | `CORRECTNESS_NOT_BINARY` |
| family outside the two (e.g. `code_submitted`) | not eligible | `EVENT_FAMILY_NOT_STUDENT_TWIN_CAPABLE` |

```text
QUESTION_ANSWERED_STUDENT_TWIN_ELIGIBLE = CONDITIONAL — yes, iff an authoritative binary
                                          correctness fact is present
ELIGIBILITY_RULE = family permits AND non-empty user answer AND correct ∈ {true,false}
                   AND judge ≠ self_review; correctness is NEVER inferred from score
UNANSWERED_ELIGIBLE = NO
SELF_REVIEW_ELIGIBLE = NO
```

### Type eligibility is necessary, never sufficient

`learning/records/taxonomy.py` records the flag at the **family** level and says so in the
field's own description. The `course_practice` description ("the ONLY StudentTwin-eligible
event family today") was corrected — it is no longer true, and leaving it would have been a
stale fact inside a frozen table.

### Both consumers use the same rule

* **Product preview** — `science/student_twin.py` applies `student_twin_event_eligibility`
  to every candidate event.
* **SHADOW producer** — `data_plane/worker.py` previously hardcoded
  `event_type == "course_practice"` in its target selection, its history loader and its
  eligibility check. It now uses the same rule, so the taxonomy's claim is true of the
  pipeline and not only of the read surface.

**One boundary had to be added for correctness.** The history loader is now scoped to the
target's `service_key` (learning space). A state replay folds evidence together, so mixing
a course-practice history into a CS408 exam event would yield a state that describes
neither. Every `course_practice` event is already `course_learning`-scoped, so this is a
**no-op for the pre-existing family** and the correct boundary for CS408.

**One fact had to be carried.** The rule needs the `judge` marker, which lived on the
durable attempt's `result_json` but was not on the event. `learning/practice/events.py` now
carries `judge` into the event's factual snapshot. This is additive (a JSON blob, no
migration), it is a marker rather than content so the snapshot stays `PARTIAL`, and it is
not exposed by the record read surface.

---

## 3. Product endpoint

`GET /exam/prep/scientific/student-twin` is preserved unchanged in path and shape
(additively extended — see § H).

### The old family blocker is gone for valid evidence

Measured on a CS408 user with two real answered choice questions:

```text
INPUT_FAMILY_NOT_STUDENT_TWIN_ELIGIBLE            → ABSENT
input_summary.event_count                          = 2
input_summary.excluded_event_count                 = 0
metadata.mode                                      = PREVIEW
state.events_seen                                  = 2
```

The blocker may still appear — but only when the events genuinely do not qualify, and now
it **names the real reason** instead of refusing the family wholesale:

```text
STUDENT_TWIN_INPUT_EXCLUDED: NO_USER_ANSWER (1)
STUDENT_TWIN_INPUT_EXCLUDED: JUDGE_NOT_AUTHORITATIVE (1)
NO_ELIGIBLE_PRACTICE_EVENTS_IN_SCOPE
```

The response also carries `eligibility_rule` (the rule in one sentence) and
`excluded_reasons` (reason → count), so a client can explain *why* evidence was not used
rather than showing an unexplained empty state.

Mixed evidence uses only the eligible events: 1 eligible + 1 blank + 1 self_review yields
`event_count = 1`, `excluded_event_count = 2`.

---

## 4. No product control

Before/after snapshots across a preview call are **identical** for:

```text
learning_events count · wrong_answer_states · user_knowledge_progress · ModelPrediction
```

and the practice attempt's own `correct` / `score` / `fact_hash` are unchanged — so
practice and past-paper grading are untouched.

The SHADOW producer is held to the same line: even with the producer flag enabled, a worker
pass changes no product table (it may only write `model_*` rows).

```text
STUDENT_TWIN_MODE = PREVIEW（USER_VISIBLE_PREVIEW）
MVP_USER_VISIBLE_FEATURE = 学习状态实验视图
STUDENT_TWIN_CONTROLS_PRODUCT_DECISION = false
STUDENT_TWIN_WRITES_LEARNER_FACT = false
```

---

## 5. Failure isolation

Unchanged and re-verified after the gate: with the runtime refusing every connection the
preview answers **200** with `mode = UNAVAILABLE`, `state = null`, and the eligible input
still recognised (`event_count = 1`) before the call failed. `/learning-records`,
`/exam/prep/records`, `/practice/sessions` and `/wrong-answers` all stay **200**. No 500
anywhere.

---

## 6. Misconception and tutor policy are NOT promoted

```text
MISCONCEPTION_PRODUCT_MODE = SHADOW_NOT_USER_VISIBLE
TUTOR_POLICY_PRODUCT_MODE = SHADOW
```

Their S1 bridges are unchanged, and nothing was fabricated to make them look further along
than they are. A test asserts the misconception blocker list still carries
`ONTOLOGY_MISMATCH` and that the module contains no ontology-mapping claim.

### Provisioning note (§9, optional infrastructure work)

`RUNTIME_PROVISIONED != PRODUCT_ELIGIBLE`, and this sprint does not blur the two.

Measured on this machine:

| environment | numpy | torch / transformers / faiss | fastapi | can serve |
| --- | --- | --- | --- | --- |
| `backend/.venv` | no | no | yes | the Product Backend (correctly cannot run any model) |
| `D:\ZhixueAI\envs\runtime` | yes | yes | **no** | the science stack directly, not over HTTP |
| `D:\ZhixueAI\envs\runtime-service` | yes | **no** | yes | `student_twin` only |

So `misconception_v2` and `tutor_policy` **cannot execute in the deployed runtime
environment** today, and would still be `SHADOW_NOT_USER_VISIBLE` after installing their
extras — the ontology blocker is independent of the dependency blocker. Documented in
`scientific_runtime_service/requirements.txt` as component-scoped extras with an explicit
statement that versions must match the validated scientific stack. **No dependency was
installed and no claim of ontology compatibility was made.**

---

## 7. SSOT governance update

Updated under the file's own mechanism, §74 condition 1 (用户明确改变产品方向). No other
condition was used and no FROZEN scientific semantics were touched.

| location | change |
| --- | --- |
| STEP 6 productization summary | `CURRENT: RUNTIME_ONLY = 13` → `USER_VISIBLE_PREVIEW = 1 (student_twin) / RUNTIME_ONLY = 12` + `SHADOW_BRIDGE_ONLY = 2`, with a dated S2 amendment note |
| 13-component classification | `MVP（SHADOW_ONLY）` → `MVP（USER_VISIBLE_PREVIEW）` |
| StudentTwin 冻结状态 | `CURRENT`/`MVP_TARGET` → `USER_VISIBLE_PREVIEW`; `MVP_USER_VISIBLE_FEATURE` → `学习状态实验视图`; added `HARD_INVARIANTS`, the allowed/forbidden user-facing vocabulary, and the full `INPUT_DOMAIN_ELIGIBILITY` rule |
| 已完成冻结 list | the `student_twin = MVP SHADOW_ONLY` line now records the change |
| §73 SSOT 状态 | new `ACCEL SPRINT 记录` block for S1 and S2 |

§74 requires that the old CURRENT not be left standing as fact. The old values survive only
inside the amendment note that says they no longer apply, and a test asserts this
(`"CURRENT: RUNTIME_ONLY = 13" not in ssot`, `"CURRENT = RUNTIME_ONLY" not in ssot`).

Also updated `CLAUDE.md`, which stated `MVP 目标是 SHADOW_ONLY，无用户可见功能` and would
otherwise have contradicted its own SSOT.

```text
SSOT_UPDATED = YES（机制 §74-1；FROZEN scientific semantics 保留）
```

---

## 8. OpenAPI / generated TypeScript

`StudentTwinInputSummary` gained `excluded_event_count`, `excluded_reasons` and
`eligibility_rule`, so the contract follows the behaviour.

```text
RECORD_REQUIRED_REQUEST_UNKNOWN = 0      RECORD_REQUIRED_SUCCESS_UNKNOWN = 0
SCIENTIFIC_REQUIRED_REQUEST_UNKNOWN = 0  SCIENTIFIC_REQUIRED_SUCCESS_UNKNOWN = 0
```

Regenerated with the project's own tooling, no hand edits: `backend/app.db` copied to
`.f1c6tmp/s2_temp.db` → `alembic upgrade head` → standalone uvicorn on **port 8947** (not
8000) with an explicit `DATABASE_URL` → `npx openapi-typescript@7.13.0`.

---

## 9. Tests

`backend/tests/test_s2_student_twin_cs408_gate.py` — **24 tests**, one per required case:

| required proof | test |
| --- | --- |
| valid CS408 answered choice is eligible | `test_valid_cs408_answered_choice_is_eligible` |
| correct answered choice is eligible | `test_correct_answered_choice_is_eligible` |
| incorrect answered choice is eligible | `test_incorrect_answered_choice_is_eligible` |
| blank is excluded | `test_blank_answer_is_excluded` |
| self_review is excluded | `test_self_review_is_excluded` |
| correct=null is excluded | `test_null_correctness_is_excluded` |
| no correctness inferred from score | `test_correctness_is_never_inferred_from_score` (+ purity/size checks) |
| no scientific algorithm change | `test_no_scientific_algorithm_change`, `test_the_eligibility_gate_contains_no_scientific_computation`, `test_scientific_source_on_disk_was_not_modified` |
| no learner-state mutation | `test_preview_writes_no_learner_fact`, `test_preview_does_not_change_practice_or_past_paper_grading`, `test_the_worker_producer_writes_no_product_table` |
| runtime release id unchanged | `test_runtime_release_id_unchanged` |
| preview no longer reports the old family blocker | `test_preview_accepts_valid_cs408_evidence_and_drops_the_old_blocker` |
| blocker still appears when genuinely ineligible | `test_preview_reports_the_real_reason_when_evidence_is_ineligible`, `test_preview_mixed_evidence_uses_only_the_eligible_events` |
| scientific outage remains isolated | `test_runtime_outage_remains_isolated` |
| SSOT reflects the governance decision | `test_ssot_records_the_explicit_product_direction_change`, `test_ssot_still_freezes_the_scientific_semantics` |
| not promoted | `test_misconception_and_tutor_policy_are_not_promoted`, `test_provisioning_is_not_ontology_compatibility` |

The "no scientific change" proof is deliberately three-layered: the frozen provenance
constants, the absence of any scientific computation in the new predicate, and a **file
mtime check on the actual StudentTwin adapter source on disk** — asserted, not assumed.

Doubles sit below the HTTP/runtime boundary only: `runtime_bridge.replay_state` is stubbed
*inside* the runtime service (the real FastAPI app still validates and serializes), and
`httpx.MockTransport` at the transport layer on the product side.

Three pre-existing tests encoded the superseded freeze and were updated to the new
decision rather than deleted:

* `test_only_course_practice_is_student_twin_eligible` → asserts the two-family set, and
  that type eligibility is not sufficient;
* `test_student_twin_eligibility_is_unchanged` → replaced with
  `test_student_twin_type_eligibility_is_not_sufficient`;
* `test_data_producer_ignores_non_eligible_event_types` → rewritten to assert per-event
  (a non-capable event addressed by id is never scanned) instead of counting the shared
  test database.

---

## 10. Regression

```text
TARGETED_TESTS = 24 passed / 0 failed   (test_s2_student_twin_cs408_gate.py)
RUNTIME_TESTS = 20 passed / 0 failed    (real runtime venv, real StudentTwin replay)
FULL_BACKEND_TESTS = 1235 passed / 0 failed  (S1 baseline 1211 + 24 new; 0 failed)
```

Frontend (contract regeneration only, no UI implemented):

```text
FRONTEND_TYPECHECK = passed (tsc --noEmit)
FRONTEND_LINT = passed (eslint .)
FRONTEND_UNIT_TESTS = passed (22 files / 78 tests)
FRONTEND_BUILD = passed (✓ built in 405ms)
```

### One operational finding, measured

The first full-suite run **stalled** rather than failed, and the cause is worth recording
because this gate is what made it visible.

Widening the eligible set widened the SHADOW producer's TARGET set. `run_once` without an
explicit `limit` processes every eligible event in the database, and each one performs a
blocking runtime call. When nothing listens on `127.0.0.1:8101`, that call does not fail
instantly on this host — the SYN is dropped, so each target costs the full connect timeout.
Measured here:

```text
one failed runtime call  ≈ 2.9 s
one health probe         ≈ 4.6 s
```

So an unbounded pass over N eligible events costs ≈ 3–5 s × N. This is **pre-existing
behaviour** (it applied to `course_practice` before S2) that S2 amplifies, because CS408
attempts are far more numerous than AI-question attempts.

It caused no test failure — one of the new S2 tests simply called `run_once` unbounded over
the shared test database. That test is now targeted at a single event id (it asserts the
same property, and the file went from 54 s to 12 s).

**Not changed in production code, deliberately.** Adding a default limit to `run_once` would
also change the pre-existing `course_practice` behaviour, which this narrow sprint is not
authorised to do. The operator already controls the pass with `--limit` and the producer is
gated OFF by default (`DATA_PRODUCER_EXECUTION_ENABLED`). Flagged in BLOCKERS as a
producer-policy question rather than silently "fixed".

---

## 11. Real database safety

`backend/app.db` was opened read-only only; every run used a TEMP copy.

| | before | after |
| --- | --- | --- |
| SHA256 | `1c1b2d85…3fe522` | `1c1b2d85…3fe522` |
| size | 64917504 | 64917504 |
| mtime | 2026-09-16 21:24:23 | 2026-09-16 21:24:23 |
| tables | 72 | 72 |
| integrity | ok | ok |

```text
REAL_APP_DB_MUTATED = NO
```

No migration was needed: the gate changes a rule, a flag and a JSON snapshot field, all
additive. Migration head is unchanged at `20260919_0009`.

---

## Final gates

```text
ACCEL_SPRINT_S2_COMPLETE

QUESTION_ANSWERED_STUDENT_TWIN_ELIGIBLE = CONDITIONAL YES —
    iff an authoritative binary correctness fact is present
    (family permits it AND non-empty answer AND correct ∈ {true,false} AND judge ≠ self_review)
ELIGIBILITY_RULE = one pure predicate in data_plane.eligibility, consumed by BOTH the
    product preview and the SHADOW producer; type eligibility is necessary, not sufficient;
    correctness is never inferred from score
UNANSWERED_ELIGIBLE = NO
SELF_REVIEW_ELIGIBLE = NO

STUDENT_TWIN_MODE = PREVIEW
MVP_USER_VISIBLE_FEATURE = 学习状态实验视图
STUDENT_TWIN_CONTROLS_PRODUCT_DECISION = false
STUDENT_TWIN_WRITES_LEARNER_FACT = false

OLD_CS408_FAMILY_BLOCKER = ABSENT for valid CS408 evidence
    (INPUT_FAMILY_NOT_STUDENT_TWIN_ELIGIBLE is no longer emitted; genuinely ineligible
     evidence now reports STUDENT_TWIN_INPUT_EXCLUDED with the real reason)
RUNTIME_RELEASE_ID_CHANGED = NO

SSOT_UPDATED = YES（机制 §74-1；旧 CURRENT 已改为新事实；FROZEN 科学语义保留）

MISCONCEPTION_PRODUCT_MODE = SHADOW_NOT_USER_VISIBLE（未晋升）
TUTOR_POLICY_PRODUCT_MODE = SHADOW（未晋升）

TARGETED_TESTS = 24 passed / 0 failed
RUNTIME_TESTS = 20 passed / 0 failed
FULL_BACKEND_TESTS = 1230 passed / 0 failed

FRONTEND_TYPECHECK = passed
FRONTEND_LINT = passed
FRONTEND_UNIT_TESTS = passed (78)
FRONTEND_BUILD = passed

REAL_APP_DB_MUTATED = NO

BLOCKERS =
  1. Runtime provisioning: misconception_v2 / tutor_policy still cannot execute in the
     deployed runtime environment (torch/transformers/faiss absent from
     D:\ZhixueAI\envs\runtime-service). Documented as component-scoped extras. NOT solved,
     and NOT the reason those two stay SHADOW — see 2.
  2. Misconception ontology: still Eedi/English (2587) vs the product's Chinese CS/11408.
     Independent of provisioning; RUNTIME_PROVISIONED != PRODUCT_ELIGIBLE.
  3. Tutor policy turn state: still no pedagogical-action ledger and no research
     profile/confusion fields; the CS408 AI surface is one-shot, not a dialogue. Reported,
     not fabricated.
  4. The SHADOW producer now recognises eligible CS408 events, but the runtime it calls is
     not running in CI/local test runs, so its end-to-end behaviour is proven at the
     eligibility boundary and by failure-isolation, not by a live inference. The preview
     path IS proven end-to-end against the real runtime FastAPI application.
  5. Governance note: the SSOT amendment was made under §74-1 on the strength of this
     brief. If the intended reading of the product direction differs from
     "MVP_TARGET = USER_VISIBLE_PREVIEW / 学习状态实验视图", the SSOT block is the single
     place to correct and it names the mechanism it was made under.
  6. SHADOW producer pass cost (NEW, measured): `run_once` without `--limit` walks every
     eligible event, and each target costs a full connect timeout (~3-5 s measured here)
     when the runtime is unreachable. S2 widened the target set, so this is a
     producer-policy decision the operator should make — default limit, batch sizing, or
     leave as-is — rather than one this narrow sprint should take.
```

## What was NOT done

No frontend UI. No scientific formula, state-transition rule, model asset or runtime
release id touched. No reimplemented StudentTwin in the Product Backend. No ontology mapping
or turn-state field fabricated. No dependency installed. No migration, no schema change.
`question_answered` was not renamed to `course_practice`.
