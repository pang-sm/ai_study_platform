# ACCEL_SPRINT_S7 — PRODUCT-NATIVE MODEL PIPELINE V1
## + EVIDENCE RELIABILITY FORENSIC CLOSURE + CS408-NATIVE KT BOOTSTRAP

**Verdict: COMPLETE — with one reversal and one refusal.**

```text
EVIDENCE_RELIABILITY_PREPROCESSING   = VERIFIED          (S5's NOT_RECOVERED is SUPERSEDED)
EVIDENCE_RELIABILITY_FINAL_MODE       = SHADOW_NOT_USER_VISIBLE
EVIDENCE_RELIABILITY_V2_REQUIRED      = YES  (trigger CHANGED: ontology, not preprocessing)
DATA_READINESS_GATE                   = FAIL
CS408_NATIVE_KT_TRAINED               = NO   (refused by the gate, as the brief requires)
REAL_APP_DB_MUTATED                   = NO
```

The sprint asked for a final provenance-grade attempt to recover the `evidence_reliability`
preprocessing, and for a native KT dataset and model. It recovered the preprocessing —
**S5's verdict was wrong, and the sprint found why**. It did not train a model, because the
product holds **no real CS408 interaction data at all** (0 users, 0 events), and the gate it
had to pass was written down before that was known.

---

## 0. FILES CHANGED

| File | Change |
|---|---|
| `backend/science/evidence_reliability.py` | scaler gate **CLOSED** by measurement; recovered standardizer recorded; `production_mode()` now requires **both** gates; blockers split into open/resolved; per-variant `b_s` mode recorded |
| `backend/science/kt_native.py` | **new** — `CS408_INTERACTION_DATASET_V1` contract, native ontology, data-quality audit, pre-registered readiness gate, split policies (user-grouped + temporal holdout), promotion gate, artifact manifest, training-stage plan, V2 decision |
| `backend/science/kt_evaluation.py` | **new** — pure-Python metrics (AUROC / accuracy / NLL / Brier / ECE + reliability bins), calibration (Platt / isotonic / temperature), and the online shadow evaluator |
| `scripts/audit_kt_readiness.py` | **new** — read-only PART C/D/E/F audit against any snapshot |
| `scripts/verify_evidence_reliability_frozen_reproduction.py` | corrected: models the per-variant `b_s` branch instead of assuming one source revision |
| `backend/tests/test_s7_native_kt_pipeline.py` | **new** — 42 tests |
| `backend/tests/test_s4_…`, `test_s5_…`, `test_s6_…` | five assertions restated (never weakened) where S7 changed a measured fact |
| `scientific_runtime_service/tests/test_evidence_reliability_scaler.py` | unchanged — its no-silent-promotion guard now takes the `reproduced` branch |

No frontend file was modified. No API contract changed. No migration was needed.

---

## PART A — EVIDENCE RELIABILITY FORENSIC RECOVERY

```text
EVIDENCE_RELIABILITY_PREPROCESSING = VERIFIED
```

### A1. What S5 concluded, and why it was wrong

S5 recovered the frozen artifact set (cohort, 3 splits, IRT parameters, alpha, 5 checkpoints,
5 per-row experiment outputs) and reported `REPRODUCTION_FAILED`: the re-derived standardizer
reproduced the BASE predictions exactly but not the reliability weights, and a free 8-parameter
fit appeared to conflict on `b_s`.

S5's forward pass followed the archived source's `if c == "b_s"` branch, which emits the
mapped value **raw**. That branch is correct for four of the five checkpoints and **wrong for
exactly one**: the base `42` run was trained with `b_s` **z-scored**. The archive therefore
contains a *later* revision of `evidence_reliability.py` than the checkpoint it was being used
to verify — and S5 measured the revision, not the run.

### A2. How S7 settled it — inversion, not fitting

For a sequence whose first emitted row is `t=1`:
`p_rel(t=1) = sigmoid(alpha · w_0 · (y_0 − 0.5))` with `theta_0 = 0`, so **`w_0` — the
network's own output at that step — is exactly recoverable** from the frozen predictions. That
isolates one network evaluation per sequence, with no recurrence error accumulated, and makes
the standardization parameters identifiable from thousands of independent equations.

Solving against those recovered `w_0`:

```text
variant        n     rmse        fitted (m, s)            code-derived (m, s)      mode
42           4519   2.03e-07   -0.536745874 / 0.653580144  -0.536745877 / 0.653580218  Z-SCORED
42_nort      4519   1.91e-07    0.000000235 / 1.000000573   (n/a — raw)              RAW
43           4710   2.03e-07   -0.000000045 / 1.000000000   (n/a — raw)              RAW
44           4529   2.07e-07   -0.000000071 / 1.000000011   (n/a — raw)              RAW
```

Two facts make this provenance rather than curve-fitting:

* the base-42 optimum **equals the pipeline's own independently re-derived train-row
  statistics to seven significant digits** — a free fit that reproduces a number nobody
  constrained would not agree with the rule that produced it;
* for the other four the optimum is **exactly the identity**, i.e. the raw column — which is
  precisely what the archived `if c == "b_s"` branch does.

### A3. Full-trajectory verification

Re-running the archived evaluator end to end with that transform, against **every** frozen
per-row value, for **all five checkpoints**:

```text
variant       split   rows    max |delta|
42            val    31160    1.788e-07       42_nort    val    31160    1.788e-07
42            test   32059    1.788e-07       42_nort    test   32059    1.788e-07
43            val    31493    1.490e-07       43         test   31238    1.788e-07
44            val    30007    1.788e-07       44         test   34145    1.788e-07
42_surprise   val    31160    1.788e-07       42_surprise test  32059    1.788e-07
-------------------------------------------------------------------------------
GLOBAL: 188,262 rows verified — worst |delta| 1.788e-07
```

`1.788e-07` is one float32 ulp at these magnitudes — the reproduction is exact to the precision
the frozen run itself used. The corrected S5 verification script now reports
`SCALER_AND_CHECKPOINT_REPRODUCE_FROZEN_OUTPUTS`.

### A4. The archive was also incomplete — and that too is now closed

Sweeping the 38 GB source archive surfaced a **complete `src/` tree that S5's extract had
dropped**: `utils/` (which carries `load_split`), `baselines/bkt.py`, `data/audit_data.py`,
`evaluation/{analysis,corruption}.py`, and the raw cohort CSV. The four files S5 *did* read are
byte-identical to the archive copies, so nothing it transcribed was wrong — the tree was simply
short of the module that defines the split.

Recovered verbatim:

```python
def load_split(project, seed):
    return pd.read_parquet(f"{project}/data/splits/split_{seed}.parquet")
```

exactly the semantics both S5 and S7 assumed. **No assumption about the train-frame selection
is left unverified.**

### A5. Was this the free fit? No.

PART A2 forbids promoting the S5 free 8-parameter reconstruction (rmse 9.3e-05). It is **not**
the basis of this verdict and is not promoted: the recovery is a closed-form inversion
corroborated by the pipeline's own rule, and `SCALER_RECOVERY_EVIDENCE.free_fit_was_not_used`
records that as data.

### A6. The gate closed — and the surface did NOT open

This is the trap the sprint had to avoid. S5's `production_mode()` returned `PREVIEW` on the
scaler gate **alone**; closing that gate would have **silently promoted the component**. It now
reads both gates, and the input gate is independently open:

```text
SCALER GATE           CLOSED   (recovered + verified + recorded)
INPUT GATE            INCOMPATIBLE
  b_s / log_opp / p_t   indexed by the scientific skill ontology
  hint_count / has_bottom_hint   no hint mechanism exists on any surface
MODE                  SHADOW_NOT_USER_VISIBLE
```

Closing the scaler gate moved the **first unsatisfied gate** from `PART A1 scaler recovery` to
`product-input compatibility`, and the product surface stayed shut. The recovered numbers are
recorded as data (`SCALER_STANDARDIZATION_PARAMS`) so the closure is usable, not merely
asserted.

---

## PART B — `CS408_INTERACTION_DATASET_V1` FROZEN

A dataset **identity**, not just an exporter: the join of contract version, catalog version,
exporter version, scope, and collection start, so two training runs can be declared
incomparable instead of assumed equal.

```text
dataset_version     CS408_INTERACTION_DATASET_V1
contract_version    kt-v1          (the S6 row contract, unchanged and not version-bumped)
export_version      kt-export-v1
exam_track_id       cs_408         (DATASET SCOPE only)
catalog_version     v2            (read from the versioned catalog)
collection_start    ACCEL_SPRINT_S6 / 2026-09-19
```

**B1 required fields** — 11 per interaction (learner ref, event id, timestamp, subject, module,
item, source type, event type, authoritative boolean, concept key, concept level) plus 8 scope
fields and 3 optional telemetry fields.

**B2 missing ≠ zero.** Every optional field is nullable, NULL means NOT OBSERVED, and the
missingness is *reported*. A real observed `0` survives as `0` and is asserted to (test:
`test_a_missing_observation_is_never_reported_as_zero`).

**B3 scope vs event.** `exam_track_id` is on the dataset, not on a fact — preserved from S6 and
asserted: no interaction carries it, and the contract states why.

---

## PART C — DATA QUALITY AUDIT

Measured read-only against the **live production snapshot** (`VACUUM INTO` copy taken
post-deployment).

```text
users_with_eligible_interactions   0
total_eligible_interactions        0
events_scanned                     0
median_sequence_length             undefined (no sequences)
module_coverage                    0 modules
chapter_coverage                   0 chapters
concept_coverage                   0 stable concepts
question_coverage                  0 distinct items
label_balance                      undefined
telemetry_missingness              undefined
duplicate_rate                     undefined
invalid_correctness_rate           undefined
timestamp_anomalies                0
PII fields present                 NONE
```

The production database holds **86 tables, 0 users, 0 learning events**. Its only non-empty
content tables are content: `exam_question_bank` (4375), `programming_exercises` (1831),
`knowledge_points` (112), materials and announcements. The local audit database is the same
(users 0; and it does not carry the canonical tables at all).

This is not a defect — it is the correct state of a product whose canonical learning-fact
schema was deployed on 2026-09-19. The canonical fact stream is the *only* thing a native KT
model may read, so the dataset is empty by construction rather than by accident.

### C1. Coverage levels are reported separately — and were a real bug

`module` / `chapter` / `concept` coverage are **disjoint buckets**, not nested. The first draft
of the audit counted chapter-level facts inside concept coverage, which would have reported a
chapter id as a concept — the exact thing C1 forbids. The test caught it; the buckets are now
disjoint and asserted (`test_module_chapter_and_concept_coverage_are_reported_separately`).

---

## PART D — MODEL TRAINING READINESS GATE

**Written before any model was fitted. Not changed afterwards.**

```text
gate_version   cs408-kt-readiness-v1        registered 2026-09-19
registered_before_training = YES
```

| threshold | value | why |
|---|---|---|
| users_with_eligible_interactions | 100 | below this, per-user behaviour is indistinguishable from the model |
| total_eligible_interactions | 2000 | below this, test metrics are not stable |
| median_sequence_length | 5 | a recurrence needs several steps per sequence |
| trainable_concepts | 20 | with fewer concepts there is almost nothing to generalise across |
| trainable_concept_min_interactions | 20 | must appear in train, dev AND test with power |
| modules_covered | 2 | one module makes per-module behaviour unmeasurable |
| minority_class_share | 0.20 | extreme skew makes a constant predictor score well |
| minimum_split_interactions / _users | 100 / 10 | or "held-out evaluation" is nominal |

`must not be lowered to unlock a result` is a field, not a sentiment, and every threshold
carries its rationale so it cannot be relaxed as "a judgement call".

```text
DATA_READINESS_GATE = FAIL
failed checks: all 6 data thresholds + all 6 split thresholds (the split is empty)
TRAINING_PERMITTED  = NO
```

A refused gate is a **result**, which is what the sprint asked to measure.

---

## PART E — SPLIT POLICY

```text
PRIMARY             kt-split-v1 (S6) — USER-GROUPED, learner in exactly one split
OPTIONAL SECOND     kt-split-temporal-v1 (new) — deployment-drift evaluation
```

**No interaction is ever split at random.** The temporal holdout cuts **per learner** by that
learner's own `occurred_at` ordering, not at a global timestamp — a global cut would put whole
learners on one side and silently degenerate into a second user-grouped split. It is a separate
policy version and is never mixed into the primary one.

```text
USER_LEAKAGE = NONE — learner_overlap_between_splits == [], asserted on a 400-learner fixture
             = overlap empty on the real (empty) production dataset
temporal: answer_is_earlier_than_holdout == True, every learner contributes to both sides
```

---

## PART F — CS408-NATIVE KT V0

```text
CS408_NATIVE_KT_TRAINED = NO
CS408_NATIVE_KT_MODEL   = NONE
NATIVE_ONTOLOGY_SIZE    = 0
```

**Not executed, because `DATA_READINESS_GATE = FAIL`.** The brief's rule is "if and only if",
and the gate was registered before the measurement, so this is the required outcome rather
than a shortfall.

**F3 native ontology (built, empty).** The mapping `native concept identity → contiguous
training index` is implemented and versioned as `cs408-native-ontology-v1`, with its
`mapping_hash` and `concept_count` persisted. It is built **from the dataset's own concept
keys** — no foreign ontology is read, and the module says so in its own payload
(`not_a_foreign_mapping`). Stability is a property, not a hope: adding a concept **appends**
an index and renumbers nothing, asserted. A foreign reuse is detectable — a non-native `kind`,
a count that disagrees with the table, or a non-contiguous index set all fail the guard.

**F2 model family.** DKT / SimpleKT / AKT are named as candidates; CGKT is **excluded** on the
F2 grounds (graph semantics not genuinely available and frozen), and the legacy
`learner_state` implementation is excluded as an input source because its `q` is an integer
index into the ASSISTments/Junyi ontology — reusing it would be the 0.46-swing mapping this
design exists to avoid.

---

## PARTS G / H — METRICS AND CALIBRATION

Implemented and verified against analytic values, in **pure Python** (the product backend has
no numpy — measured, and kept that way):

```text
AUROC perfect 1.0 · inverted 0.0 · ties 0.5 · single-class None
log loss matches manual computation exactly
ECE: perfectly calibrated 0.0 · anti-calibrated 1.0
reliability bins reported so the number can be inspected
per-group metrics carry sample counts and REFUSE to score a group below min_n
```

A single-class sample returns **`None`, not 0.5** — reporting chance would invent a result.

**Calibration** is fitted on `dev` **only**, evaluated on an untouched `test`, and the
provenance (method, params, fit-split digest, `calibrator_hash`, `fitted_on`, `evaluated_on`)
travels as data. All three methods are deterministic and bounded; an unknown method is refused.

```text
BASELINE_METRICS     = NOT_COMPUTED (no data)
MODEL_TEST_METRICS   = NOT_COMPUTED (no model)
CALIBRATION_METRICS  = NOT_COMPUTED (no model)
```

No metric is reported from synthetic data as a result.

---

## PART I — PROMOTION GATE

```text
PROMOTION_MAX_MODE = SHADOW
```

The predicate carries the nine required conditions as data and **defaults to refusing**. Even
with every condition evidenced it still refuses without an explicit final gate decision, so
`USER_VISIBLE_PREVIEW` is never reached by a model merely existing. Asserted both ways
(`test_promotion_cannot_exceed_shadow_without_an_explicit_decision`).

## PART J — ARTIFACT PACKAGING

```text
MODEL_ARTIFACT       = NONE (no model trained)
ONTOLOGY_ARTIFACT    = NONE (no concepts observed)
CALIBRATOR_ARTIFACT  = NONE (no model)
```

The manifest contract is built and tested: 10 required artifact kinds, every entry carrying its
own `sha256`, bundle-relative refs only — an absolute path is detected and reported, because a
manifest that points at one machine's filesystem is not a manifest.

## PARTS K / L / M — RUNTIME AND SHADOW WIRING

```text
SCIENTIFIC_RUNTIME_ENDPOINT = NONE_ADDED
PRODUCT_SHADOW_ENDPOINT     = NONE_ADDED
PRODUCT_MODE                = NO_PROMOTION — every component exactly as S6 left it
```

All three parts are conditional on a trained model existing. None does. The legacy
`learner_state` component was **not** overloaded and remains distinct, as required. No new
transport was introduced; no endpoint was added.

## PART N — ONLINE EVALUATION READINESS

```text
ONLINE_SHADOW_EVALUATOR = ARMED_NOT_RUNNING
```

The deterministic evaluator is built and tested. It pairs a shadow prediction with the
**earliest authoritative response from the same learner on the same concept strictly after**
`predicted_at` — the *next* response, not any response.

Its governing refusal: a prediction with no later response is **excluded and counted**
(`NO_LATER_AUTHORITATIVE_RESPONSE`), never scored as a miss — "not observed yet" and "we were
wrong" are different results and only one of them is evidence. A non-boolean verdict is not a
target. Another learner's response is never this learner's target. Output is independent of
input order. It writes nothing (`wrote_learner_fact = False`, asserted against the database).

It is **armed, not running**: with no model in shadow there are no predictions, and an empty
comparison is reported as `n = 0` rather than as a result.

## PART O — EVIDENCE RELIABILITY V2 DECISION

```text
classification  PRODUCT_NATIVE_RETRAIN_REQUIRED     required = YES
```

**The trigger changed.** S5's trigger was preprocessing loss. S7 recovered and verified the
preprocessing, so that trigger no longer applies. The trigger now is that the checkpoints
consume `b_s` / `log_opp` / `p_t`, all keyed by the scientific skill ontology the product has
no honest mapping onto — an **input-domain** fact, which no amount of recovery fixes.

The old checkpoint family is **retained as verified research provenance**: not retrained under
the same name, not superseded in place, and still `SHADOW_NOT_USER_VISIBLE`. Reusable from the
old work: the architecture, the objective, and the recovered standardizer (for reproducing the
old runs). Not reusable: the feature semantics and the ontology.

## PART P — DATA PRIVACY

```text
PII fields present in the export   NONE   (asserted against the real payload)
learner reference                  16-char sha256 digest over a fixed domain — not the user id
```

Forbidden fields are checked against **the sequences that were actually produced**, not against
a promise. `username`, `email`, `display_name`, question text, answers, analysis, explanations,
source code, AI prompts and responses, filesystem paths and session secrets are all excluded.

A first draft scanned the whole document and matched the body's own `forbidden_fields`
declaration, reporting every prohibition as a violation of itself. The check is now scoped to
the payload, where a leak would actually be.

## PART Q — PRODUCTION SAFETY

```text
PRODUCT_BACKEND_HEAVY_IMPORTS = ZERO
```

Measured in a **subprocess**: importing `science.kt_native`, `science.kt_evaluation` and
`science.evidence_reliability` pulls in **no** numpy, torch, scipy, sklearn, pandas or
transformers. A second test asserts no module under `backend/science/` contains a training
import at all. Training is defined as **offline-only** in the training-stage contract.

## PART R — TESTS

```text
backend/tests/test_s7_native_kt_pipeline.py   42 passed
```

Covering every required property: deterministic export · scope metadata · missing ≠ zero ·
user-split isolation · ontology stability · no foreign ontology reuse · no PII · baseline
evaluation · calibration split isolation · artifact hashes · shadow writes no learner fact ·
cross-user isolation · failure isolation · heavy imports zero.

Five pre-existing assertions were **restated, never weakened**, where S7 changed a measured
fact. One deserves naming: S5's `test_a_promotion_requires_more_than_the_scaler_gate` asserted
*"if the scaler gate passed, features must be compatible"* — a statement about a state that
could not occur. S7 made it occur, and it failed, revealing the assertion was backwards. It now
asserts what it was reaching for: the scaler gate is a **precondition, never a sufficient
condition**.

Two tests found real defects during development (a `None` row crashing the evaluator's sort
key; chapter coverage nested inside concept coverage). Both are fixed, not worked around.

## PART S — REGRESSION

```text
TARGETED_TESTS (S7)                 42 passed
RUNTIME_TESTS  service venv         31 passed / 3 skipped
RUNTIME_TESTS  torch, scaler         9 passed  (204 s)
REAL_MODEL_TESTS torch              17 passed
FULL_BACKEND_TESTS                1482 passed / 0 failed  (634 s)
FRONTEND_TYPECHECK                  PASS
FRONTEND_LINT                       PASS
FRONTEND_UNIT_TESTS                 84 passed (24 files)
FRONTEND_BUILD                      PASS (842 ms)
```

**A note on the frontend, because it moved during the sprint.** An intermediate unit-test run
showed `80 passed / 4 failed` in `cs408-student-twin-workspace.test.tsx` — a file being edited
**concurrently by a non-S7 frontend change** (it had no modifications when this session opened,
and by the end of the sprint `student-twin.ts`, the component and its CSS were all modified
too). Those 4 failures were that change's test running ahead of its component, and they cleared
on their own once it landed. S7 touched no frontend file and no API contract
(`frontend/src/types/api.ts` is byte-identical), and left that work alone throughout.

---

## BLOCKERS

1. **`DATA_READINESS_GATE = FAIL`** — the product holds 0 users and 0 learning events. This is
   the expected state of a schema deployed on 2026-09-19, and the first blocker for every
   downstream part.
2. **The trainer body is not implemented** — deliberately. Every other stage is built, tested
   and gated; the training stage is defined as a contract that **refuses** (`permitted: false`,
   `refused_by: DATA_READINESS_GATE`, `implemented: false`). Writing a trainer with no data to
   validate it against would ship unvalidated scientific code, and the brief's own rule is
   "train if and only if the gate passes".
3. **`evidence_reliability` input remains `INCOMPATIBLE`** — `b_s` / `log_opp` / `p_t` are
   keyed by the scientific skill ontology. The scaler gate is closed; this one is not, and it
   is not closeable by recovery.
4. **`computer_network` concept coverage is 0%** (S6, unchanged) — its stored concept ids embed
   their display titles, so 875 questions can reach chapter level only. A content defect.
5. **`has_bottom_hint` / `hint_count` remain `NOT_AVAILABLE`** — no hint mechanism exists.
6. **`response_time_ms` still has no producer** (S6, unchanged) — no CS408 surface records a
   per-item serve boundary.
7. **A concurrent frontend change is in flight** (not S7's). It caused 4 transient unit-test
   failures mid-sprint that cleared when it landed. Reported so the next reader does not
   attribute them to this sprint.
8. **Scratch could not be deleted.** My probe directory `D:/ZhixueAI/research_extract/.s7probe/`,
   the extracted tree `s7_full/`, the archive index and two `%TEMP%` files were refused deletion
   by the permission layer (same as S6). They should be removed.
9. **Prior-sprint untracked scratch remains**: `.bc7tmp/`, `.bc8r1tmp/`, `.bc8tmp/`, `.f1c5qa/`,
   `.f1c6tmp/`, `frontend/.f1c5qa/`, `frontend/.f1c6tmp/`, `test-results/`, `backend/file`.

---

## WHAT THE SPRINT ACTUALLY ESTABLISHED

**A reversal, earned by measurement.** S5 concluded a required input was absent from the
archive. It was not: the standardizer is re-derivable from the frozen bytes, and every one of
188,262 frozen prediction rows across five checkpoints now reproduces to float32 exactness. The
cause of the earlier verdict was a mis-modelled forward pass against a source revision from
after the checkpoint it was verifying — found by inverting the frozen outputs instead of
trusting a branch, and corroborated by the pipeline's own rule agreeing with the recovered
parameters to seven significant digits.

**A refusal, earned by a threshold written first.** The native model was not trained, because
the pre-registered gate failed on real data — and the gate was registered before the numbers
were known, which is the only order in which a readiness threshold means anything.

**A near-miss caught.** Closing the scaler gate would have silently promoted the component to
`USER_VISIBLE_PREVIEW`, because the mode was derived from that gate alone. It now reads both
gates. Nothing was promoted; every component sits exactly where S6 left it.

```text
DATA_FLYWHEEL_ACTIVE = YES
FIRST_UNSATISFIED_GATE (evidence_reliability) = PRODUCT_INPUT_COMPATIBILITY
FIRST_UNSATISFIED_GATE (native KT)            = DATA_READINESS_GATE
```
