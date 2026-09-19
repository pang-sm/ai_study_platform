# ACCEL_SPRINT_S3 — learner_state Model Productization + Scientific Producer Outage Hardening

Date: 2026-09-19. Repository: `C:\Users\26477\Desktop\ai_study_platform`.
Mode: accelerated scientific productization. **No frontend UI was implemented.**

```text
ACCEL_SPRINT_S3_COMPLETE
```

Baseline: ACCEL_SPRINT_S2 = COMPLETE. Full backend regression: **1235 → 1257 passed / 0 failed**
(this sprint added exactly 22 tests; no pre-existing test changed behaviour).

**Headline:** the producer outage is hardened, and `learner_state` was **audited with the real
model, measured, and then honestly rejected for the product surface**. It is the wrong model to
productize *today* — not because it fails to run, but because the product cannot honestly form
its input. The gate was NOT lowered.

---

## PART A — Producer outage circuit breaker

### The operational problem, restated precisely

`worker.run_once` makes **one blocking runtime call per ELIGIBLE target**. With the runtime
unreachable, that is the *same* failure repeated once per target, at ~3–5 s each (measured;
previously recorded in S2). A run over N eligible events pays N × timeout for one fact.

### The decision, implemented as stated

No new default `--limit`. Instead: on the **first confirmed `ScientificUnavailable`** in a run,
stop processing further scientific targets for that run.

The signal had to be made distinguishable first. `backend/data_plane/runtime_client.py` now
separates two classes that were previously collapsed into `RuntimeClientError`:

```text
ScientificUnavailable  ->  RuntimeUnavailableError(RuntimeClientError)   # an OUTAGE
ScientificRejected     ->  RuntimeClientError                            # our request was refused
```

That distinction is the whole design. An outage fails identically for every remaining target and
must stop the run; a **contract mismatch is per-target** (a product-side bug for that payload)
and must *not* halt the run. `test_contract_violation_is_not_treated_as_an_outage` holds that
line.

### What the stop guarantees

```text
no fake Prediction for the failing target ....... nothing is written
failed item marked scientifically processed ..... NO (no row of any kind)
remaining items ................................. untouched
next run ........................................ retries all of them
```

`run_once` now returns a factual outcome rather than an ambiguous partial success:

```text
runtime_unavailable       bool
outage                    {component, target_event_id, detail} | null
targets_not_attempted     int   (counted with the pure eligibility predicate — no runtime call)
```

`run_loop` aggregates the same fields (`runtime_unavailable` is OR'd, `outage` keeps the first).

### Explicitly unchanged

```text
DEFAULT_LIMIT_ADDED = NO
--limit semantics = unchanged (still selects TARGETS; history is never truncated)
healthy-runtime processing = byte-for-byte unchanged
course_practice behavior when the runtime is healthy = unchanged
```

`test_no_default_limit_was_added` asserts the signature default stays `None` and that no
`DEFAULT_LIMIT` constant exists, so the breaker cannot quietly become a cap.

---

## PART B/D — learner_state: the real runtime audit

`learner_state` is **not** StudentTwin. StudentTwin is a deterministic rule engine; `learner_state`
is a **learned** knowledge-tracing model family. They are different components, different
sciences, different contracts, and were treated as such.

### What was inspected, and what was found

| Item | Finding |
|---|---|
| Runtime adapter | `zhixue_runtime/components/adapters/learner_state.py` — 5 families |
| Families | `DKT` (LSTM), `SimpleKT` (causal transformer), `AKT` (monotonic attention), `CGKT` (GCN+transformer), `CGKT_v2` (relational attention) |
| Model assets | 39 real checkpoints under `model_assets/v1/learner_state/` |
| Checkpoint provenance | `artifact.json`: `source_repo=coursegraph_kt`, `source_commit=06d4366`, `research_status=frozen`, `production_role=candidate` |
| Feature requirements | `q` (concept index sequence) + `r_prev` (0/1 previous-response sequence) |
| Input ontology | `base` = ASSISTments **123** skills; `junyi` = **835** concepts |
| Output | `next_response_probability` — P(correct on the next response) |
| Calibration | `scientific_threshold = null` in the frozen acceptance record |
| Variant mode | PANEL — `averaging=false`, `auto_selection=false`, `active_product_variant=null` |
| Dependencies | `torch` (+ numpy) |

### Measured, not assumed

The real checkpoints were **executed** in the frozen model environment
(`D:\ZhixueAI\envs\runtime`, torch 2.14.0+cpu):

```text
LOADED: True
num_skills per family: {'DKT': 123, 'SimpleKT': 123, 'AKT': 123, 'CGKT': 123, 'CGKT_v2': 835}
AKT    ontology=base  next_response_probability=[0.638484, 0.526288, 0.821003, ...]
CGKT   ontology=base  next_response_probability=[0.529145, 0.634802, 0.936401, ...]
DKT    ontology=base  next_response_probability=[0.441045, 0.436590, 0.829950, ...]
SimpleKT ontology=base next_response_probability=[0.671785, 0.682544, 0.817419, ...]
CGKT_v2 ontology=junyi next_response_probability=[0.277978, 0.624077, 0.768626, ...]
PANEL averaging: False  auto_selection: False  active_product_variant: None
```

All **39 / 39** checkpoint SHA-256 values match the frozen artifact. **No retraining was
performed, and none is required.**

---

## PART C/E — Semantics, and the domain-compatibility verdict

### Frozen semantic (carried through verbatim)

```text
learner_state estimates: P(correct on the learner's NEXT response)

It is NOT: mastery probability | knowledge mastery | exam-pass probability
           | question difficulty | student ability score
```

### VERDICT: `BLOCKED`

Not "PARTIAL". The distinction matters and is the core finding of this sprint.

* The frozen **component matrix** (`backend/data_plane/eligibility.py`) records
  `learner_state = ("PARTIAL", "ONTOLOGY_MISMATCH", "ONTOLOGY_MISMATCH")`, and the readiness
  audit records `ontology_mapping: NONE`. The SSOT **§36.13** already states
  *"目前存在 ontology gap"*. **This sprint confirms the SSOT; it does not overturn it.**
* "PARTIAL" describes the *presence* of an interaction sequence. It does **not** mean the
  sequence can be fed to the model. The question PART E asks — *can real CS408 product facts
  honestly form the **exact** model input?* — is answered **NO**.

The product can honestly supply: an ordered sequence, an authoritative boolean correctness
fact, and the item each observation belongs to. The model additionally requires **an integer
index into ITS OWN ontology**. The product has Chinese CS408 knowledge points. There is no
mapping, and the index is not a cosmetic detail — it selects the embedding the model learned
for a specific ASSISTments skill or Junyi concept.

### Why "just assign an index" is fabrication, measured

Feeding CS408 concepts through an invented index is exactly the "no invented latent feature"
rule PART E states. To show it is not a bookkeeping concern, the real model was run on the
**same learner, same real correctness sequence, same CS408 concepts**, changing only the
arbitrary index assignment:

```text
CS408 concepts     : ['os.paging', 'os.deadlock', 'ds.binary_tree', 'net.tcp_congestion']
correctness (real) : [0, 1, 0, 1]
mapping A          : [3, 17, 42, 5]
mapping B          : [61, 2, 99, 30]

DKT        P(next correct) A=0.362997  B=0.438057  |delta|=0.075060
SimpleKT   P(next correct) A=0.401796  B=0.863032  |delta|=0.461236
AKT        P(next correct) A=0.753926  B=0.867081  |delta|=0.113155
CGKT       P(next correct) A=0.735000  B=0.937240  |delta|=0.202240
```

The "prediction" moves by up to **0.46** as a function of a number we made up. It would be an
artifact of the mapping, not a property of the learner. On the product surface that is a
fabricated number wearing a scientific label — the precise failure mode this platform forbids.

---

## PART F — Runtime provisioning: deliberately NOT performed

PART F is conditioned on *"if learner_state is scientifically compatible"*. **It is not.**
The precondition therefore fails, and no dependency was installed.

```text
installed into backend/.venv ......... nothing (torch/transformers/faiss/numpy/sklearn/zhixue_runtime: ZERO)
installed into the serving venv ...... nothing
```

The reasoning is not merely procedural. Installing ~2.5 GB of `torch` into the serving venv to
run a model that **cannot be honestly fed product data** would be engineering effort spent
papering over a product-data gap — which the project's own readiness audit forbids
(*"do not paper over them with engineering hacks"*).

The existing architecture already covers this case honestly. Heavy components are exposed as
endpoints that lazily import their stack and **degrade to a bounded 503**; `misconception_v2`
and `tutor_policy` already behave this way (documented in
`scientific_runtime_service/requirements.txt`). `learner_state -> torch` was added to that
same list.

---

## PART G — Scientific Runtime endpoint

```text
POST /v1/inference/learner-state
```

Added to `scientific_runtime_service/`, using the real model through the runtime's public
adapter registry (`get_adapter("learner_state")`) — **no formula is duplicated anywhere**, and
the Product Backend imports none of it.

```text
Request                             Response
  contract_version                    contract_version, request_id, runtime_release_id
  request_id                          component_id = "learner_state"
  family       (explicit, required)   scientific_source_class, scientific_source_commit
  q            [int] concept indices  family, ontology, num_skills
  r_prev       [int] 0/1              next_response_probability  [float]
  mask         [float]? optional      score_semantics, engineering_representative_only
                                      active_product_variant, product_role
                                      controls_product_decision, latency_ms
```

Two contract decisions worth stating:

* **`family` is explicit and required.** The adapter is a PANEL that never averages, votes, or
  auto-selects; requiring the caller to name the architecture keeps that true at the wire.
* **The endpoint accepts indices only, and maps nothing.** It cannot be handed a product
  concept. This is the runtime half of the domain finding:
  `test_index_outside_the_ontology_is_rejected_not_clamped` proves an out-of-range index is
  **refused**, not silently bent into a meaning.

Malformed input is a 4xx (caller's fault); a missing heavy dependency is a bounded 503.

---

## PART H/L — Product Backend bridge

`backend/science/learner_state.py` (new) uses the **existing ONE transport**
(`backend/science/client.py`). No second HTTP path was created.

```text
GET /exam/prep/scientific/learner-state          (authenticated, bounded)
```

**It produces NO number, by design.** With no honest input there is no honest inference, so no
inference is attempted. The response is the restrained, factual statement PART L asks for:

```text
metadata                component, mode, controls_product_decision, writes_learner_fact,
                        generated_at, blockers, semantics
score_semantics         the frozen next-response meaning, with every wrong reading negated
next_response_probability   null   (null in every response this mode can produce)
model_requirement       what the model needs, what the product has, what is missing
evidence_window         the REAL canonical facts, and what the input rule rejected
runtime_reachable       null by default; bounded probe only via ?probe_runtime=true
runtime_provenance      runtime path, source commit, model_executes=true,
                        executed_for_this_request=false
```

### Naming: `prediction` was deliberately NOT used

`backend/science/contract.py` states the project's own semantic gate: *"Deliberately absent from
every model here: `probability`, `confidence`, `mastery`, `prediction`, `diagnosis`."* PART L
lists `prediction` as an illustrative field; the project rule forbids that **name**. The
project rule wins, and the field is named after the model's actual output. A test asserts no
field is named after any forbidden reading, and that prose may only mention a wrong reading in
order to deny it.

### Wording

`掌握度` / `掌握` does not appear anywhere in the response (asserted). The permitted user-facing
concept, `下一次作答正确概率（实验）`, is carried **inside the model-requirement block** with an
explicit note that it is not surfaced in this mode — it documents the only allowed framing for a
future surface, and no number accompanies it.

### Failure isolation (PART M)

The default path makes **no runtime call at all**, so it cannot cascade. The optional
`?probe_runtime=true` uses the client's bounded `health()` (which answers "unavailable" rather
than raising) and is *additionally* wrapped, so even an unforeseen probe failure reports
`runtime_reachable=false`. A runtime outage can never become a product 500:
`test_runtime_outage_never_becomes_a_product_failure` covers both the realistic down-runtime
shape and an exploding probe.

---

## PART I/J/K — Authority mode and the gate

```text
LEARNER_STATE_PRODUCT_MODE = SHADOW_NOT_USER_VISIBLE
LEARNER_STATE_CONTROLS_PRODUCT_DECISION = false   (permanent)
LEARNER_STATE_WRITES_LEARNER_FACT = false         (permanent)
```

Never `ACTIVE` in this sprint; never `PREVIEW`. The PART J gate was applied literally and two
of its six conditions **fail**:

| # | Condition | Result |
|---|---|---|
| 1 | CS408 input domain is honest | **FAIL** — no ontology mapping exists |
| 2 | Runtime actually executes the real model | PASS — measured |
| 3 | Checkpoint/model provenance valid | PASS — 39/39 sha256 verified |
| 4 | Output semantics exactly next-response P(correct) | PASS |
| 5 | Calibration/validity gate satisfied | **FAIL** — `scientific_threshold = null` |
| 6 | No learner-fact mutation | PASS |

Conditions 1 and 5 are **independent**; either alone closes the surface. The gate was not
lowered, and no number was published for a competition deadline.

PART K is structural rather than promised: with no prediction produced, there is nothing that
*could* change knowledge status, wrong state, plan, grading, question selection, model routing,
or a tutor response. `test_no_learner_fact_mutation` proves the endpoint leaves
`learning_events`, `model_predictions` and `model_inference_runs` untouched.

---

## PART N — misconception_v2 / tutor_policy untouched

No attempt was made to promote either. Confirmed from code, not assumed:

```text
MISCONCEPTION_PRODUCT_MODE = SHADOW_NOT_USER_VISIBLE   (unchanged)
TUTOR_POLICY_PRODUCT_MODE  = SHADOW                    (unchanged)
```

Their semantic blockers remain independent of provisioning, and this sprint changed neither
their science nor their mode.

---

## PART O/P — Tests

### Targeted S3 (new) — `backend/tests/test_s3_learner_state_gate.py`

```text
22 tests, 22 passed
```

Circuit breaker: first-outage stop · no faked prediction · failed item left unprocessed ·
remaining targets untouched · next run retries · healthy semantics unchanged · explicit
`--limit` unchanged · no default limit · contract violation does not trip the breaker ·
outage is a distinct error class.

learner_state: frozen matrix verdict · no invented mapping · no scientific computation in the
gate module · authentication · no number produced · no mastery wording · evidence window counts
real canonical facts · cross-user isolation · no learner-fact mutation · failure isolation ·
bounded probe · OpenAPI concrete · heavy-imports zero.

### Scientific Runtime

```text
scientific_runtime_service/tests/  (runtime-service venv) ....... 24 passed, 1 skipped
test_learner_state_real_model.py   (runtime venv, real torch) ... 7 passed
```

The real-model file executes the actual checkpoints, verifies all 39 checkpoint hashes against
the frozen artifact, asserts the frozen ontology sizes, asserts determinism, asserts the
no-averaging/no-auto-selection panel property, and asserts an out-of-ontology index is
rejected. It runs where torch exists and **skips** elsewhere rather than degrading into a mock.

The two venv splits are honest and deliberate: `test_api.py` needs `fastapi` (service venv);
the real-model file needs `torch` (model venv). Neither venv can do both — the same environment
fact this project has measured before.

### Full regression

```text
backend: pytest  ->  1257 passed / 0 failed
```

### Frontend (PART P; no UI implemented)

```text
FRONTEND_TYPECHECK    = PASS
FRONTEND_LINT         = PASS
FRONTEND_UNIT_TESTS   = 82 passed (24 files)
FRONTEND_BUILD        = PASS
```

`frontend/src/types/api.ts` was regenerated (the project requires it after an API change) from a
temporary backend on port **8947** with a **TEMP `DATABASE_URL`** (a copy of `app.db`), never the
real DB and never port 8000. The regeneration contributed **exactly one operation**
(`/exam/prep/scientific/learner-state`) plus its schemas — 170 lines, verified to contain no
unrelated drift. The file already carried large pre-existing drift against `HEAD`
(350 → 383 operations before this sprint); that drift is **not** from this work.

---

## Safety

```text
REAL_APP_DB_MUTATED = NO
```

`backend/app.db` sha256 `1c1b2d8538d7a3c52a79a64dec904c69c6ec964b86decbc6508d0d2a438fe522`
— **identical before and after**. `PRAGMA integrity_check` = `ok`.

Every test binds an explicit temp `DATABASE_URL` via `conftest.py`. No `git reset / clean /
checkout / restore / stash / commit / merge / rebase / pull / push` was run. No worktree was
created. All scratch probes and the temporary spec directory were deleted.

Read-only observation on the real DB (for context, not changed by this sprint): it holds
`exam_question_bank = 9333`, `programming_exercises = 1923`, `knowledge_points = 32`, and has
**no** `learning_events` / `model_predictions` / `model_inference_runs` tables — i.e. it is not
migrated to the data-plane schema. Consistent with the recorded `MIGRATION_HEAD = 20260917_0008`
gap; no migration was attempted.

---

## Findings the user must decide on (not self-applied)

1. **SSOT §49 `CURRENT Scientific Runtime` is stale — pre-existing, and this sprint widens it.**
   It lists `/health`, `/v1/capabilities`, `/v1/inference/student-twin`. The service already
   served `misconception-v2` and `tutor-policy` **before** this sprint, and now serves
   `learner-state` as well. Per the governance rule (*"若发现 SSOT 内部存在 stale 的 CURRENT
   段落，报告给用户并等待决定"*) the SSOT was **not** rewritten.

2. **No SSOT state number changed.** `USER_VISIBLE_PREVIEW` remains `1` (student_twin);
   `learner_state` remains non-visible. The sprint's verdict **confirms** §36.13's existing
   "ontology gap" rather than altering it, so no §74 update condition was triggered.

3. **The real blocker is product-data work, not engineering.** Closing `learner_state` requires
   an ontology mapping (or a product-native ontology the model could be trained on properly,
   with a calibration gate recorded). Until then, any number it produced would be the artifact
   measured in PART E.

---

## Final gate values

```text
ACCEL_SPRINT_S3_COMPLETE

PRODUCER_RUNTIME_OUTAGE_CIRCUIT_BREAKER = YES — stops at first confirmed ScientificUnavailable
DEFAULT_LIMIT_ADDED = NO
HEALTHY_PRODUCER_SEMANTICS_CHANGED = NO

LEARNER_STATE_COMPONENT = real learned knowledge-tracing PANEL (DKT/SimpleKT/AKT/CGKT/CGKT_v2)
LEARNER_STATE_DOMAIN_COMPATIBILITY = BLOCKED — ontology mapping NONE (ASSISTments 123 / Junyi 835 vs CS408)
LEARNER_STATE_RUNTIME_PROVISIONED = YES — adapter + 39 real checkpoints + POST /v1/inference/learner-state
LEARNER_STATE_REAL_MODEL_EXECUTION = YES — MEASURED, 5 families, 39/39 checkpoint sha256 verified

LEARNER_STATE_ENDPOINT = POST /v1/inference/learner-state (runtime) + GET /exam/prep/scientific/learner-state (product)
LEARNER_STATE_PRODUCT_MODE = SHADOW_NOT_USER_VISIBLE
LEARNER_STATE_OUTPUT_SEMANTICS = next_response_probability P(correct on the learner's NEXT response)

LEARNER_STATE_CONTROLS_PRODUCT_DECISION = false
LEARNER_STATE_WRITES_LEARNER_FACT = false

MISCONCEPTION_PRODUCT_MODE = SHADOW_NOT_USER_VISIBLE (unchanged)
TUTOR_POLICY_PRODUCT_MODE = SHADOW (unchanged)

PRODUCT_BACKEND_HEAVY_IMPORTS = ZERO — torch/transformers/faiss/sklearn/sentence_transformers/zhixue_runtime

TARGETED_TESTS = 22 passed / 0 failed
RUNTIME_TESTS = 24 passed + 1 skipped (service venv) ; 7 passed (real model, torch venv)
FULL_BACKEND_TESTS = 1257 passed / 0 failed

FRONTEND_TYPECHECK = PASS
FRONTEND_LINT = PASS
FRONTEND_UNIT_TESTS = 82 passed
FRONTEND_BUILD = PASS

REAL_APP_DB_MUTATED = NO

SCIENTIFIC_FRONTEND_NEXT_READY = NO — learner_state produces no displayable number; student_twin PREVIEW remains the only user-visible scientific surface

BLOCKERS = ONTOLOGY_MAPPING_ABSENT (product CS408 concepts -> ASSISTments 123 / Junyi 835)
           CALIBRATION_GATE_NOT_ESTABLISHED (scientific_threshold = null)
           torch not installed in the serving venv (bounded 503; PART F precondition unmet)
           SSOT §49 endpoint list stale (pre-existing) — awaiting user decision
```
