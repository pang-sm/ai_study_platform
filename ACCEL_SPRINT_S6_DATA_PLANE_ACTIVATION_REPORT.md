# ACCEL_SPRINT_S6 — PRODUCTION DATA-PLANE ACTIVATION + SCIENTIFIC DATA FLYWHEEL LAUNCH

**Verdict: COMPLETE — deployed and verified in production.**

```text
DEPLOYED_COMMIT                 9eb98645
PRODUCTION_SCHEMA_REVISION      20260919_0010
LOCAL_REAL_APP_DB_MUTATED       NO
```

The sprint's premise held, with one correction that mattered: the migration chain **could
not run on any deployed database** as it stood, and the rehearsal found it before the
deployment did. Details in PART D2.

---

## 0. FILES CHANGED

| File | Change |
|---|---|
| `backend/core/schema_preflight.py` | **new** — read-only startup gate: revision + required-column check |
| `backend/main.py` | preflight called **before** `create_all` |
| `backend/learning/practice/service.py` | `attempt_index` derived from a real canonical count on the live path |
| `backend/learning/practice/telemetry.py` | `TELEMETRY_CONTRACT` + schema/collection version |
| `backend/science/concept_coverage.py` | **new** — CS408 concept-coverage audit (measurement only) |
| `backend/science/kt_dataset.py` | `exam_module_id` / `source_type` per interaction; scope-level `exam_track_ids`; `user_grouped_split` |
| `migrations/guards.py` | **new** — idempotent DDL helpers |
| `migrations/env.py` | repository root on `sys.path` |
| `migrations/versions/2026*_0001…0007` | `create_table` / `create_index` / `add_column` made idempotent |
| `scripts/deploy/check_schema.py` | **new** — operator-facing schema check |
| `scripts/export_kt_dataset.py` | **new** — deterministic offline exporter |
| `.github/workflows/deploy.yml` | migration + schema verification inserted between backup and app start |
| `docs/DEPLOYMENT_RUNBOOK.md` | **new** |
| `backend/tests/test_s6_deployment_gate.py` | **new** — 35 tests |
| `backend/tests/test_s6_data_flywheel.py` | **new** — 30 tests |
| `backend/tests/test_s5_evidence_reliability_and_flywheel.py` | one assertion restated for the S6 contract |

---

## PART A — MIGRATION BEFORE APPLICATION START

```text
APPLICATION_CAN_START_BEFORE_MIGRATION = NO
```

Two independent enforcements, so neither alone is the guarantee:

1. **The deployment script** runs `alembic upgrade head` after the verified backup and
   before `systemctl restart ai-backend`, then re-reads the database. Order is asserted by
   `test_the_deployment_migrates_before_it_starts_the_application`.
2. **The application** refuses to start on a database that is behind. The preflight runs
   at import, *before* `Base.metadata.create_all`, because after `create_all` a fresh
   database and an unmanaged legacy one are no longer distinguishable in shape.

Measured, on a byte-for-byte copy of the real `backend/app.db`:

```text
import main  against the un-migrated copy   -> SchemaBehindError   (refused)
import main  against the migrated copy      -> OK, 394 routes
```

## PART B — SCHEMA COMPATIBILITY PRECHECK

`backend/core/schema_preflight.py`. Read-only: no DDL, no revision stamping, no
`create_all`. Two checks, per the brief's "Alembic revision + required-column":

- **revision** — the script head is *derived from the revision files*, not hard-coded, and a
  branched chain is refused rather than guessed;
- **columns** — the eight columns the ORM selects that only a migration adds, each carrying
  the revision that introduces it, so the error names the smallest fix.

Four states, and only two pass:

| state | meaning | outcome |
|---|---|---|
| `NOT_PARTICIPATING` | no product tables — new file, fresh install, test database | ALLOWED |
| `AT_HEAD` | stamped at head **and** no required column missing | ALLOWED |
| `BEHIND_HEAD` | stamped at another revision | REFUSED |
| `UNMANAGED_PRE_EXISTING` | product tables, no `alembic_version` — **every deployed database** | REFUSED |

`AT_HEAD` alone is not enough: a database stamped at head whose column was removed by hand
is still one the ORM cannot read, and that case is refused too. `ZHIXUE_SCHEMA_PREFLIGHT`
accepts `enforce` (default) / `warn` / `off`; an unknown value is treated as `enforce`.

Observed operational error, verbatim, on a copy of the real database:

```text
SCHEMA PREFLIGHT FAILED - this deployment must not start.
  database state : UNMANAGED_PRE_EXISTING
  database revision : (none - no alembic_version)
  required revision : 20260919_0010
  missing columns the ORM selects:
    ai_requests.service_namespace  (added by 20260915_0006)
    ...
  FIX: back up the database, then run
         alembic -c alembic.ini upgrade head      (from the repository root)
```

## PART C — CREATE_ALL REMAINS NON-AUTHORITATIVE

```text
CREATE_ALL_PRODUCTION_SCHEMA_MUTATION = 0
```

`create_all` is still called at import, and at head it contributes **no table** —
`test_create_all_contributes_no_table_at_head` measures this on the migrated copy. Schema
ownership is Alembic's; the preflight is what makes that true rather than aspirational,
because `create_all` cannot add a column to a table that already exists.

## PART D — REAL LEGACY DB MIGRATION REHEARSAL

Full sequence on a **byte-for-byte copy** of `backend/app.db`, in subprocesses:

```text
preflight (refuse) -> app import (refuse) -> alembic upgrade head -> schema check (AT_HEAD)
-> integrity_check ok -> application start -> CS408 surfaces -> StudentTwin
```

Every CS408 surface answers **200** and every pre-existing table keeps every row. The real
`backend/app.db` is asserted unchanged by sha256 / size / mtime at the end.

## PART D2 — THE REHEARSAL THAT FOUND A REAL DEFECT

The local `backend/app.db` is **not** the production database, and rehearsing only on it
would have been a false negative. Production has **81** tables (it grew from the deployed
application over months); the local audit file has **71**. Comparing them showed that
production already holds `learning_events`, `model_predictions`, `model_inference_runs`,
`model_versions`, `subscriptions`, `usage_budgets`, `usage_ledger`, `ai_requests`,
`ai_cost_records` — all created by `create_all`, with no `alembic_version` anywhere.

Revisions `0001` and `0002` created those tables with a **bare `op.create_table`**. Run
against production they would have raised `table learning_events already exists` on the
first statement — after the backup, with the application already stopped. The deployment
would have failed and left the site down.

**Fix:** `migrations/guards.py` makes the chain idempotent. A guard adopts an existing
table rather than aborting, and **refuses** if that table is missing a column the revision
declares — skipping is only honest when the table already has what the revision says.
Nothing changes on a fresh database: the table is absent, so the DDL runs identically. The
revision ids and chain order are untouched.

Verified against a **consistent snapshot of the live production database**
(`VACUUM INTO`, because production runs in WAL mode and a plain file copy silently misses
the un-checkpointed tail — 5 tables exist only in the WAL):

```text
before : 81 tables   integrity ok
after  : 86 tables   integrity ok   revision 20260919_0010
dropped: NONE
created: alembic_version, exam_prep_profiles, practice_attempts, practice_sessions,
         wrong_answer_states
row-count changes across ALL 81 pre-existing tables: NONE
```

`test_the_chain_adopts_tables_that_create_all_already_created` reproduces the class of
failure in CI so it cannot come back.

## PART E — MIGRATION ROLLBACK SAFETY

**No downgrade is rehearsed, and none is claimed.** `20260919_0009` and `20260919_0010`
raise `NotImplementedError` on downgrade: dropping the telemetry columns destroys the only
record of what a measured duration was measured between. `DEPLOYMENT_RUNBOOK.md` §4 says so
explicitly rather than implying an Alembic downgrade would be lossless.

What is tested instead:

- the pre-migration backup is a complete, restorable database (integrity ok, table count);
- restoring it returns the pre-migration shape exactly;
- the failure path names the command (`alembic -c alembic.ini upgrade head`) and does **not**
  start the application;
- the migration log is the revision evidence, produced by Alembic itself.

## PART F — TELEMETRY ACTIVATION

Emission is from the **real business source**, not frontend analytics. The envelope's only
projection is `AttemptTelemetry.to_fact_fields()`, its only production consumer is
`learning.practice.service.record_attempt`, and no frontend module constructs one (the sole
occurrence of the name in `frontend/src` is the generated request type).

Audited per flow:

| flow | writes telemetry via | status |
|---|---|---|
| CS408 question answer (live) | `POST /practice/sessions/{id}/attempts` → practice service | **ACTIVE** |
| CS408 chapter practice | `learning/practice/adapters/exam.py` (mirrored) | columns present, NULL by design |
| CS408 past papers | `learning/practice/adapters/exam.py` (mirrored) | columns present, NULL by design |
| course practice | `learning/practice/adapters/course.py` (mirrored) | columns present, NULL by design |
| programming exercise | `learning/practice/adapters/programming.py` (mirrored) | columns present, NULL by design |

| field | SOURCE_OF_TRUTH | UNIT | NULL SEMANTICS | FROM |
|---|---|---|---|---|
| `response_time_ms` | **none yet** — no per-item serve boundary is recorded on any surface | integer ms | NOT OBSERVED (a real 0 is a different fact) | column `20260919_0010`; no producer |
| `response_time_source` | the writer, via `AttemptTelemetry.duration_source` | enum token | provenance unknown | `20260919_0010` |
| `attempt_index` | `record_attempt` — counted over canonical `practice_attempts` for the same learner and question identity | 1-based ordinal ≥ 1 | NOT OBSERVED (NULL ≠ 1) | **`ACCEL_SPRINT_S6`** |

`attempt_index` is the one field whose quantity the server actually observes, and the live
path now derives it instead of waiting for a caller who never comes. **Mirrored attempts
keep NULL**: during a replay the rows already present are an artifact of the import order,
so an ordinal counted from them would describe the import rather than the learner. No
historical value is inferred anywhere, and no value was backfilled.

## PART G — VERSIONED DATA AVAILABILITY

```text
TELEMETRY_SCHEMA_VERSION            attempt-telemetry-v1
TELEMETRY_COLUMNS_SINCE_REVISION    20260919_0010
TELEMETRY_COLLECTION_START_VERSION  ACCEL_SPRINT_S6
TELEMETRY_COLLECTION_START          2026-09-19 (deployment 9eb98645)
```

The three are recorded separately on purpose. The columns existed from `0010`; nothing
wrote them until S6. A row written in between has the columns and NULL in them, and that
NULL means **not observed** — never zero. `TELEMETRY_CONTRACT` states this per field and
travels inside the dataset body, so a future model can separate *historical missing* from
*observed zero*.

## PART H — PRODUCT-NATIVE CS408 DATASET CONTRACT

First frozen schema (`kt-v1`). Minimum fields, per learner-sequence:

| field | present | note |
|---|---|---|
| anonymous user key | ✓ | `learner_ref`, fixed-domain sha256, 16 chars |
| ordered timestamp | ✓ | `occurred_at`, epoch seconds |
| attempt / event id | ✓ | `attempt_ref` = deterministic event id |
| `exam_subject_id` | ✓ | from the dedicated `subject_key` column |
| `exam_module_id` | ✓ | **added by S6** — it was lost whenever a fact resolved to a knowledge point |
| stable native concept key | ✓ | `concept_key` + `concept_level`, deepest truthful level |
| question / item identity | ✓ | `item_ref` |
| authoritative `correct` | ✓ | exactly `True`/`False`; anything else excluded and counted |
| source type | ✓ | **added by S6** — `source_type` + `event_type` |
| `exam_track_id` | **NOT per fact** | see below |
| optional telemetry | ✓ | only where observed; both halves of a duration travel together |
| PII | **none** | asserted against `FORBIDDEN_FIELDS` |

**`exam_track_id` conflict, reported not resolved.** The brief lists it among the minimum
fields; the frozen S5 rule says a track is **never** recorded on a fact, because it is the
learner's own bundle choice and two learners who answered the same question under different
bundles must produce byte-identical facts. S6 preserves the frozen rule and reports the
track at **scope** level instead — derived from the versioned catalog, which is a statement
about the subject, not about the learner. For CS408 the track and the subject are both
`cs_408`, so nothing is lost today; for a multi-track subject the distinction would matter,
and that is the case a future sprint must decide.

## PART I — CONCEPT COVERAGE AUDIT

Measured against the product's own canonical concept space (the `code` values of
`backend/seed_data/knowledge_maps/<module>_11408.json`). A question carries a concept only
when the id it stores **equals** a canonical leaf code — nothing is normalised, stripped or
fuzzily matched, and **no mapping was generated**.

```text
module                 active  concept   %      chapter  module-only  leaf codes
data_structure          1010    1010   100.00%      0         0           32
computer_organization   1265    1200    94.86%      0        65           28
operating_system        1180    1120    94.92%      0        60           18
computer_network         920       0     0.00%    875        45           28
-------------------------------------------------------------------------------
TOTAL                   4375    3330    76.11%    875       170
```

The computer_network result is the finding. Its `knowledge_point_id` stores
`"<code> <title>"` — the numeric code concatenated with the display name — which is exactly
the title-as-identity that `native_concept` forbids. 875 of its questions therefore resolve
to a **chapter** and never to a concept. `data_structure` / `computer_organization` /
`operating_system` can train a concept-level model today; `computer_network` can train a
chapter-level one and cannot train a concept-level one until its id space is corrected —
which is a content decision, not something this audit may make.

Coverage is a **ceiling on trainable interactions**, not evidence that a model would be
good. It counts what the content can carry and says nothing about how many attempts exist.

## PART J — DATASET EXPORT V1

`scripts/export_kt_dataset.py` (`EXPORTER_VERSION = kt-export-v1`). Same snapshot + same
exporter version → **byte-identical file**, asserted by running the exporter twice against
one TEMP database and comparing the output strings.

Three properties make it hold, each a decision: ordering is `(occurred_at, event_id)` within
a sequence and `(learner_ref, concept_key)` across sequences; the JSON is canonical (sorted
keys, fixed separators); and the body carries **no wall clock** — `generated_at` is
deliberately absent because it would change every second and make the hash meaningless. The
split travels inside the file but outside the hashed body. No random split inside the
exporter. Nothing is trained.

## PART K — TRAINING SPLIT POLICY

```text
TRAIN_TEST_SPLIT_POLICY = kt-split-v1   (defined, NOT executed)
```

Grouping key is the learner. The invariant that matters — **a learner appears in exactly one
split** — holds by construction, because a sequence is already one learner's interactions
and a learner's split is a property of the learner alone. Measured: `learner_overlap_between_splits == []`.

Assignment is a per-learner hash, not a shuffle. A shuffle is deterministic only for a fixed
input list; the moment a new learner is recorded every position shifts and the splits are
silently re-cut. A hash keeps a learner in their split as the cohort grows, at the cost of
approximate shares (target 70/15/15, measured 72/13/15 on 200 synthetic learners) — and the
shares are reported so the approximation is visible.

**Temporal evaluation is a different policy and is not defined here.** Splitting by time
answers a different question and must cut by `occurred_at`; it gets its own policy version
when it is required. Individual interactions are never split across train and test.

## PART L / M — EVIDENCE RELIABILITY

```text
EVIDENCE_RELIABILITY_PRODUCT_MODE      SHADOW_NOT_USER_VISIBLE
UNVERIFIED_SCALER_USED_FOR_INFERENCE   NO
EVIDENCE_RAW_FEATURE_COLLECTION        CONTRACT_RECORDED; NO NEW PRODUCER ADDED
```

The mode is **derived from the gate** (`production_mode()` reads
`SCALER_RECOVERY_METHOD`), so the two cannot drift apart. The gate still refuses:
`NOT_RECOVERED` is not among the accepted methods. No numeric result is exposed to users,
and `SCIENTIFIC_THRESHOLD` remains `null` — no calibration was ever established and none was
invented. The unverified standardizer is applied nowhere.

Raw features are described with their per-feature product classification and are unchanged
by S6. **One honest nuance:** S6 now produces the attempt ordinal, which is the raw quantity
`attempt_gt1` needs — but `attempt_gt1` counts re-attempts *within one problem presentation*
in the source's domain, while the product's `attempt_index` counts attempts on the same
*question* across sessions. Producing a related quantity is not satisfying a feature, so the
classification stays where S5 froze it and the semantic question is left to be answered on
its own evidence.

## PART N / O — STUDENT TWIN AND THE OTHER COMPONENTS

```text
STUDENT_TWIN_PRODUCT_MODE       USER_VISIBLE_PREVIEW  (runtime mode "PREVIEW")
LEARNER_STATE_PRODUCT_MODE      SHADOW_NOT_USER_VISIBLE
MISCONCEPTION_PRODUCT_MODE      SHADOW_NOT_USER_VISIBLE
TUTOR_POLICY_PRODUCT_MODE       SHADOW
```

No promotion in S6. Every component reports `controls_product_decision = false` and
`writes_learner_fact = false`, asserted for all 13. `capabilities.summary()["totals"]["user_visible"] == 1`.

StudentTwin's factual event stream is verified end to end on the migrated TARGET database:
two new eligible CS408 facts → `input_summary.event_count = 2` → the **real** scientific
runtime reached → `mode = PREVIEW`, `controls = false`, `writes = false`, no authority
increase.

## PART P — DEPLOYMENT RUNBOOK

`docs/DEPLOYMENT_RUNBOOK.md`. Contains, in order: backup → drain → migration command →
schema check → backend start → frontend deploy → health → authenticated smoke → rollback
decision point. No secrets. It also records two operational traps found during this sprint:

- **WAL.** Production runs in WAL mode with an un-checkpointed tail. The deploy's
  stop-then-copy order is what makes its backup complete; a manual `cp` while the service
  runs silently misses committed transactions. Hot backups must use `VACUUM INTO`.
- **The write gate is per-path.** `DATA_PLANE_WRITE_ENABLED` gates the course-learning
  emitter only. CS408 (`exam_prep`) and programming events are not gated, so the CS408
  flywheel does not depend on it.

## PART Q — PRODUCTION DEPLOYMENT

```text
PRODUCTION_BACKUP        app.db.before-catalog-reform.20260919_212649.db
PRODUCTION_MIGRATION     20260915_0001 -> 20260919_0010, all 10 revisions
PRODUCTION_DEPLOYMENT    SUCCESS (run 35445703581, commit 9eb98645)
PRE_DEPLOY_MIGRATION_PROOF  consistent snapshot of the live database, 81 -> 86 tables,
                            0 rows lost, integrity ok, application start verified
```

The application itself then refuses to start on a database that is behind, so a silent
"deployed but broken" outcome is not reachable.

## PART R — POST-DEPLOYMENT ACCEPTANCE

Live instance:

```text
ai-backend         active            zhixue-runtime  active
deployed commit    9eb98645          revision        20260919_0010
tables             86                integrity       ok
/health            200               /api/health     200
/exam/prep/catalog 200 (public)      /exam/prep/records        401 (auth required)
HTTPS /api/health  200               /exam/prep/scientific/student-twin  401
```

Authenticated journey + a new factual learning action, executed against a **consistent
snapshot of the live post-deployment database** (`VACUUM INTO`, so the live instance was
read and never written):

```text
register 200 / login 200
CS408 overview 200 | knowledge 200 | plan 200 | practice 200 | past papers 200
wrong answers 200 | records 200 | Student Twin 200 | KT dataset audit 200
new factual action: 2 attempts -> practice_attempts ordinals [1, 2]
learning_events: 2 rows, attempt_index [1, 2], correct {false, true}
records visible: 2      kt dataset interactions: 2 (hash f1668e4298133b69)
student twin: 2 eligible events -> real runtime -> mode PREVIEW, controls false,
              writes false
```

```text
PRODUCTION_SMOKE = PARTIAL
```

Honest scope: health, HTTPS, schema, and every **public** surface were verified on the live
instance. The **authenticated** surfaces and the new learning action were verified on a
snapshot of the live database rather than on the running instance, because no production
credentials were held and the stored QA sessions in `.playwright/.auth/` expired on
2026-09-11. Runbook §3.2 is the checklist to close that last gap with a real account.

## PART S — DATABASE SAFETY

```text
LOCAL_REAL_APP_DB_MUTATED   NO
```

sha256 / size / mtime unchanged, asserted at the end of the rehearsal suite. Every
migration was executed on copies. The production pre-migration backup and migration log are
retained on the server and named in the runbook §5.

## PART T — REGRESSION

```text
FULL_BACKEND_TESTS   1441 passed / 0 failed   (568s)
FRONTEND_UNIT_TESTS  82 passed (24 files)
   typecheck         PASS
   lint              PASS
   build             PASS (827ms)
PLAYWRIGHT           5 passed (smoke: render, a11y, 404, responsive ×2, exam nav)
```

S6 adds 65 tests (`test_s6_deployment_gate.py` 35, `test_s6_data_flywheel.py` 30). One S5
assertion was restated rather than weakened: it asserted `attempt_index is None` for a bare
live attempt, which is precisely the behaviour S6 changes; it now asserts that the recorded
ordinal equals the real canonical count, which is the S5 invariant that actually matters.
The generated `frontend/src/types/api.ts` was **regenerated and is byte-identical** — S6
introduced no API contract change.

---

## BLOCKERS

1. **`response_time_ms` has no producer.** No CS408 surface records a per-item serve
   boundary, and a duration without a boundary is not a duration. Closing this needs a
   product change (a recorded serve timestamp, or a client that measures a monotonic
   interval and sends it) with its own design — deliberately not invented here.
2. **`log_rt` / `log_opp` / `b_s` / `p_t` remain `SEMANTICALLY_INCOMPATIBLE`** — they are
   indexed by the scientific skill ontology, and no honest mapping exists.
3. **`has_bottom_hint` / `hint_count` remain `NOT_AVAILABLE`** — no hint mechanism exists on
   any CS408 practice surface.
4. **`computer_network` concept coverage is 0%** — its stored concept ids embed their
   display titles. 875 questions can reach chapter level only. This is a content defect that
   must be fixed in the question bank; it is not fixable by mapping.
5. **`evidence_reliability` scaler remains `NOT_RECOVERED`** (S5 PART A1) — a required
   input column is absent from the frozen archive. Promotion stays blocked.
6. **`learner_state` remains blocked** — no ontology mapping, no calibration gate (S3).
7. **Production authenticated smoke is PARTIAL** — see PART R. Needs a real account.
8. **`.bc7tmp/`, `.bc8tmp/`, `.bc8r1tmp/`, `.f1c5qa/`, `.f1c6tmp/`, `frontend/.f1c5qa/`,
   `frontend/.f1c6tmp/`, `test-results/`, `backend/file`** remain untracked in the working
   tree (prior-sprint scratch, not committed). They were left in place rather than deleted.
9. **A consistent snapshot of the production database remains on this machine** at
   `%TEMP%\s6-posts-*` (copy of live user data) and scratch directories at
   `%TEMP%\s6-*`; deletion was refused by the permission layer. They should be removed.

```text
DATA_FLYWHEEL_ACTIVE = YES
```

The three spaces now record canonical, concept-tagged, correctness-bearing facts with
versioned provenance; the dataset contract, the deterministic export and the learner-grouped
split are frozen; and every component that consumes them is still exactly as gated as it was
before the sprint.
