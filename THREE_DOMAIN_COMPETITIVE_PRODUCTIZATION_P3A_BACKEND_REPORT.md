# THREE_DOMAIN_COMPETITIVE_PRODUCTIZATION_P3A_BACKEND_REPORT

Task: `THREE_DOMAIN_COMPETITIVE_PRODUCTIZATION_P3A_BACKEND`
Date: 2026-09-20
Scope: the first batch of genuinely competitive abilities — Deep Study / Strong Reasoning,
the Programming Debug Agent, and the Unified Review foundation — all on the EXISTING unified
architecture. No second AI system per space, no second quota system, no schema change, no
commit, no deploy.

---

## 1. WHAT WAS BUILT (new files)

| File | What it is |
|---|---|
| `backend/learning/deep_study.py` | the ONE strong-reasoning workflow (retrieval → bounded evidence → orchestrator → citations) |
| `backend/routers/deep_study.py` | `POST /ai/deep-study` + the typed response contract |
| `backend/learning/spaces/programming/ai.py` | Programming's narrow adapter onto `ai.orchestrator` (mirrors course/exam) |
| `backend/learning/spaces/programming/agent.py` | the bounded debug agent: loop, bounds, trace, events |
| `backend/routers/programming_agent.py` | `POST /programming/agent/debug` + the typed trace contract |
| `backend/learning/review.py` | the unified review projection over existing facts |
| `backend/routers/review.py` | `GET /review`, `GET /review/summary` |
| `backend/tests/test_p3a_strong_reasoning.py` | 8 tests |
| `backend/tests/test_p3a_programming_agent.py` | 8 tests |
| `backend/tests/test_p3a_unified_review.py` | 8 tests |

Edited (all additive): `usage/capabilities.py`, `ai/pool.py`, `ai/cost.py`,
`learning/records/taxonomy.py`, `learning/records/producers.py`, `prompts.py`, `rag.py`
(one new optional parameter), `main.py` (router registration only).

`GET /ai/models` now answers for both new capabilities (validated against
`pool.ALL_CAPABILITIES`, gated by the same tier policy, serving the same qualified subset).

---

## 2. P1_2_FINAL_SUITE

```
./.venv/Scripts/python.exe -m pytest -q          (backend/, TEMP DATABASE_URL)
1624 passed, 2 skipped, 0 failed in 2146.55s (0:35:46)
```

Green before P3A started, with `backend/app.db` byte-identical before and after (see §11).
No P1.2 change was reverted or weakened by P3A; the P3A edit set is additive.

---

## 3. STRONG_REASONING

**Capability** `tutor.strong_reasoning`.

* **Tier policy** (`usage/capabilities.py`): Standard + Advanced. Free is denied and the
  denial happens BEFORE any retrieval work or any event — a denied capability is an ANSWER,
  not a degraded answer.
* **Model pool** (`ai/pool.py`): no provider was re-benchmarked and no pool entry changed.
  The capability is served through the already qualified deep-work profile
  (`CAPABILITY_QUALIFICATION_PROXIES["tutor.strong_reasoning"] = "report.generate"`), so a
  Standard learner is answered by the qualified mid-tier deep model and an Advanced learner
  gains the premium thinking models — the pool's OWN ladder, unchanged.
* **Reservation sizing** (`ai/cost.py`): `EXPECTED_OUTPUT_TOKENS["tutor.strong_reasoning"] =
  1500` (the endpoint's default `max_tokens` is 2400), so a long reasoned answer does not
  surface as a reservation overage.
* **Execution path**: `learning.spaces.course_learning.ai.execute_course_ai` /
  `learning.spaces.exam_prep.ai.execute_exam_ai` → `AIOrchestrator` →
  permission → router → estimate → reserve → gateway → actual → settle. The module requests a
  capability by name and never names a provider or a model (asserted by a static test).

---

## 4. DEEP_STUDY

`POST /ai/deep-study`

**Input**: `question` (required), `service_key` (`course_learning` | `exam_11408`),
`course_id` / `subject_key` / `chapter_id` / `knowledge_point_id`, `material_ids[]`
(max 20), `max_tokens`.

**Workflow**: build the space's canonical `LearningContext` → resolve the material scope →
retrieve evidence → assemble a bounded evidence context → one strong-reasoning call → emit
the canonical events → return the structured answer.

* **Retrieval is the EXISTING one**: `rag.retrieve_chunks_for_materials` (explicit materials)
  or `rag.search_relevant_material_chunks` (FTS5/BM25 + keyword bonus, with the existing
  keyword fallback when FTS is unavailable). **No vector database was introduced.**
* **Bounded evidence**: the existing `trim_chunks_for_prompt` / `MAX_TOTAL_CONTEXT_LEN`
  (5000 chars) and `MAX_TOP_K` (6) bounds apply unchanged.
* **Course-scoped search** uses `course_identity_forms(course_id)` through a new ADDITIVE
  `course_ids` parameter on `search_relevant_material_chunks` — a course stored under two
  exact spellings is searched as ONE course, and nothing else matches. (Existing callers pass
  neither parameter and behave exactly as before.)
* **Exam-scoped search** uses the module's `subject_key` via the existing `subject_key`
  filter.
* **Prompt** is `prompts.build_deep_study_messages`, built ON TOP of
  `prompts.build_system_prompt` (so the evidence rules and markdown contract do not fork) plus
  one deep-study instruction block. Prompts stay out of business code.

**Response** (typed in `/openapi.json`): `answer`, `citations[]`, `material_refs[]`,
`materials {requested, used, excluded}`, `capability`, `run_id`, `request_id`, `status`,
`context` (namespace + course/module/knowledge-point identity), `model`
(`display_name`, `selection`, `tier`, `quality_class`, `options[]`), `usage`
(credits + tokens + `usage_source`), `evidence {chunk_count, material_count, retrieval}`.

**Isolation**: explicit `material_ids` are admitted only when the material is the caller's own
(and, in a course context, belongs to that course) or is a system material that explicitly
allows public RAG; the refused ones are reported in `materials.excluded`. The no-materials
path is course/module-scoped in SQL. Asserted: a stranger's material and another course's
material are both refused and never appear in a citation.

---

## 5. CITATION_MODEL

* A citation is the **same shape the chat product already persists**
  (`main.serialize_reference_item`: `material_id`, `filename`, `subject`, `file_type`,
  `snippet`, `score`, `created_at`) — one citation contract, not a second one.
* `material_refs[]` is one entry per MATERIAL (a material cited by three chunks appears once).
* **A citation can only name a chunk that was actually retrieved for this request**, and
  retrieval is only ever handed the already-validated material scope. There is no path from
  the model's prose to a citation: citations come from the retrieval result, never from the
  answer text.
* Empty evidence is a legitimate, stated outcome: `evidence.chunk_count = 0`,
  `citations = []`, `materials.used = []`, and the prompt tells the model to say the material
  does not cover the question instead of inventing a source.

---

## 6. PROGRAMMING_AGENT

`POST /programming/agent/debug` — capability `programming.agent` (Standard + Advanced, served
through the already qualified `programming.debug` profile).

**Workflow** (one bounded loop, five step actions in a closed vocabulary):

```
tests_before → diagnose → propose_patch → run_tests → (repair cycle ×N) → explain
```

* **Execution is the EXISTING backend through ONE seam**
  (`agent.execute_exercise_tests` → `main._run_official_exercise_tests`): languages, the
  official/public test bundle, the sandbox, the per-execution timeouts and the hidden-test
  rule are all unchanged. The agent passes a working copy in the runner's own file shape.
* **Every agent execution runs the PUBLIC suite only** (`submission=False`), exactly as a
  learner's own "test" action does. The hidden tests are never executed on the agent's path,
  so the agent cannot reveal what the learner is not allowed to see.
* **Advisory**: the learner's stored files are never modified (asserted by test — the project
  file is byte-identical after a run). The patch is applied to an in-memory copy only.
* **No false claims about the learner**: an agent-run execution does NOT emit `code_tested` /
  `code_run` / `code_submitted` for the learner, because it did not test the learner's own
  saved code. Those families keep their ONE producer (the real learner action).
* **Scope**: WHO is the session; WHICH CODE is the caller's own project for that exercise or
  the caller's own submitted files. A file is identified by a name that must match one of the
  run's own files (exact relative path or an unambiguous basename) — a path, a `..`, or
  another project's file is refused and the step fails as `unusable_patch`.

**Response** (typed): `agent_run_id`, `status` (`completed` | `failed` |
`no_repair_needed`), `reason`, `stop_reason`, `steps[]` (index, action, status,
`ai_request_id`, capability, latency, credits, tests result, file, bounded diff),
`iterations_used`, `executions_used`, `tests_before`, `tests_after`, `proposed_patch`,
`patch_file`, `final_code`, `diagnosis`, `patch_summary`, `explanation`, `usage`.

---

## 7. AGENT_LIMITS

```
MAX_ITERATIONS        = 3        repair cycles
MAX_EXECUTIONS        = 4        tests-before + one run per cycle
MAX_MODEL_STEPS       = 7        hard cap on model invocations
MAX_WALL_CLOCK_SECONDS= 240      the agent stops STARTING steps after this
MAX_FILES = 8 · MAX_FILE_CHARS = 12 000 · MAX_CODE_CHARS = 20 000 · MAX_DIFF_LINES = 60
```

* Every bound is checked BEFORE a step starts, so a step already in flight cannot push the
  workflow past a bound. Per-execution timeouts stay the existing runner's.
* A patch that never helps terminates at the caps with `stop_reason ∈ {max_iterations,
  budget_exhausted}` and `status="failed"` — asserted by a test that always fails the tests.
* A submission whose tests already pass produces `no_repair_needed` and **calls no model at
  all** (asserted) — the agent never invents a defect.
* **Settlement/cancellation**: every model step is its own request with a deterministic id
  `{run_id}:{step_index}:{action}` (≤ 64 chars) — its own reserve, its own settle (or release
  on a no-usage failure). A step that fails is RECORDED in the trace with its status and
  latency and is settled by the orchestrator, not left `reserved`. If steps already ran, the
  endpoint returns 200 with `status="failed"` plus the trace (the facts that happened are not
  hidden); if NOTHING ran, the real 403/429/502 is re-raised.
* The capability is checked BEFORE the baseline test run, so a tier without the capability
  never has its code executed on the way to a refusal (asserted).

---

## 8. UNIFIED_REVIEW

`GET /review`, `GET /review/summary` — read-only, no writes, no schedule computation.

| Source | Reads | Bucket |
|---|---|---|
| course wrong answers | `wrong_answer_states`, namespace `course_learning`, status `active` | `needs_attention` (no stored date) |
| exam wrong answers | the same table, namespace `exam_prep` | `needs_attention` |
| knowledge review dates | `user_knowledge_progress.review_due_at` (a STORED date) | `due` / `scheduled` |
| programming | `programming_exercise_progress` (`needs_work`, or last submit failed) | `needs_attention` |

**ReviewItem** (typed): `id`, `service_namespace`, `domain_context`,
`source_type` (`wrong_answer` | `knowledge_review` | `programming_exercise`), `source_id`,
`question_identity`, `title`, `summary`, `review_status`, `due_at`, `due_source`,
`last_attempt_at`, `reason`, `metrics`, `deep_link`.

**Anti-fabrication, enforced**:

* `due_at` is populated ONLY from `user_knowledge_progress.review_due_at`, and `due_source`
  names that exact column. A knowledge row with NO stored date contributes **no item at all**
  (asserted) — the product has no schedule for it and none is invented.
* Wrong answers / programming never receive a due date: they are `needs_attention` with
  `due_at = null` (asserted for the whole bucket).
* No `mastery_score`, no interval estimation, no memory score, no AI weakness guess. The
  module carries no such field and a test asserts the payload has no prediction-shaped key.
* The projection resolves **no question content** (deliberate): `title`/`summary` are built
  from stored, safe columns (course, module display, knowledge-point title, exercise title,
  counts) and `deep_link` points at the domain page that already renders the content safely.
  Resolving stems here would have created a SECOND question-materialization surface — exactly
  what P1.2 closed.

**Filters**: `service_namespace` (course_learning | exam_11408 | programming, aliases
accepted), `status` (`due` | `needs_attention` | `scheduled`), `course_id`, `exam_module_id`,
`language`, `limit`/`offset`. Isolation is by user first, always; the filters only narrow.

**Deep links** (to routes that already exist in the frontend): `/course/{course_id}/wrong`,
`/exam/cs408/wrong?module=…`, `/course/{course_id}/knowledge`,
`/exam/cs408/knowledge?module=…`, `/programming/{language}/exercises/{id}`.

**Summary** counts over the SAME projection (one code path, so the page and the summary can
never disagree — asserted).

---

## 9. CAPABILITY_INTEGRATION

* Two capabilities added to `CAPABILITY_TIER_POLICY` (standard + advanced). FREE is
  unchanged: `learning_plan`/`learning_report` and the free capability set are untouched.
* `ai/pool.py ALL_CAPABILITIES` gained both names (so `/ai/models` accepts them and the pool's
  own coverage invariant holds — they resolve raw on `qwen3.8-max`, which carries
  `ALL_CAPABILITIES`), and both are routed through **qualification proxies** rather than a new
  benchmark. `POOL_VERSION` / `POOL_QUALIFICATION_LEVEL` are NOT changed: no model was
  re-qualified and no entry was edited.
* `ai/cost.py`: per-capability expected output sizing added for both.
* **No second quota**: no `strong_reasoning_quota`, no `programming_agent_quota`, no new
  table, no new membership row. Both are ordinary capabilities of the unified chain
  `Subscription → Capability Permission → Usage Budget → Model Router → Gateway`.

---

## 10. USAGE_INTEGRATION

* Deep Study: exactly ONE request per call — one `ai_requests` row, one reserve, one settle,
  plus the release of the unused reservation difference (the frozen STEP7B model: one reserve
  entry per budget period). Asserted on the ledger amounts.
* Agent: ONE request per model step, each with its own reserve/settle (or release). The
  workflow's cost is the sum of its steps' settled credits (`usage.actual_credits`), and the
  response reports both `model_steps` and `execution_steps`.
* A failed step's request is RELEASED (no billable usage) rather than left reserved —
  asserted. A partial workflow therefore neither over-bills nor leaks a reservation.
* Deterministic ids `{run_id}:{index}:{action}` make the whole workflow auditable per step in
  `ai_requests` (latency from `started_at`→`finished_at`, provider/model, terminal status)
  without a second workflow table.

---

## 11. EVENTS

Five new canonical families, all `ACTIVE` (each has a real producer today, which is the only
condition this taxonomy recognises), all `student_twin_eligible=False`, all `USER_FACING`
(they ARE study history — `audit_only_event_types()` is still exactly `["ai_called"]`, and
`student_twin_eligible_types()` is still exactly the two practice families):

| Event | Namespace(s) | Producer |
|---|---|---|
| `strong_reasoning_requested` | course_learning, exam_prep | `learning.deep_study.run_deep_study` |
| `strong_reasoning_completed` | course_learning, exam_prep | the same |
| `programming_agent_started` | programming | `learning.spaces.programming.agent.run_debug_agent` |
| `programming_agent_completed` | programming | the same |
| `programming_agent_failed` | programming | the same |

* **`review_completed` was NOT emitted**: the taxonomy already declares it, as `DEFERRED`
  with source "review_items (not built)", and P3A builds a review READ projection only — there
  is no review-completion action this round, so emitting it would violate
  "NO SOURCE → NO EVENT". The name stays reserved.
* **No duplicate family**: `ai_called` remains the ONE accounting fact for every model call
  (including each agent step); the new families are the STUDY facts. A request the TIER
  refuses emits no study fact at all (the permission pre-check runs before the event); a
  request the tier allowed but the BUDGET then refused keeps the `requested` fact — the
  session really did start — and gets no `completed` fact, with `ai_called` carrying the
  denial. Same rule for the agent: `started` is emitted once the tier permits, and a run
  that cannot proceed is closed by `programming_agent_failed`.
* **§34 respected**: `envelope.assert_payload_is_safe` forbids code/prompt/response/answer
  text in a payload, so the agent's per-step trace is stored CODE-FREE (step index, action,
  status, latency, credits, the AI request id that served it, the exercise's own test result,
  and a patch's SIZE — chars/lines added/removed). Asserted: the completed event's payload
  contains neither the source code nor the prompt.
* `service_namespace` and the domain context are correct per fact: course facts carry
  `course_learning`, exam facts `exam_prep` (with `exam_subject_id`/`exam_module_id`), and
  agent facts `programming` (with the language). Asserted.

---

## 12. TESTS

New: **24 tests** across three files, all green.

* `tests/test_p3a_strong_reasoning.py` (8): free-tier denial records nothing; the full billed
  lifecycle (one request, reserve→settle with the released difference, both events, correct
  namespace); grounded citations; a stranger's material refused; another course's material
  refused; space-scoped retrieval never crosses courses; the exam space runs in its own
  context; the new capabilities are served by `/ai/models`; no provider is reachable from the
  module sources.
* `tests/test_p3a_programming_agent.py` (8): the repair loop end to end (with the learner's
  file proven untouched); hard bounds; `no_repair_needed` with no model call; another
  learner's project is a 404; a file outside the run is refused (`unusable_patch`, no
  execution); the tier gate runs before any code executes; a failed step is recorded and
  settled (settled + released); the durable trace is persisted code-free.
* `tests/test_p3a_unified_review.py` (8): course + exam wrong-answer mapping; programming
  mapping (needs_work + failed submission); three-space isolation by filter; no cross-user
  leakage; a due date exists only where one is stored; no-schedule domains stay
  `needs_attention`; the summary counts exactly what the list serves; no prediction-shaped
  field is exposed.

**Full backend suite with P3A** (TEMP DATABASE_URL, same command as §2, run over the FINAL
tree — every file listed in §1 included):

```
./.venv/Scripts/python.exe -m pytest -q          (backend/)
1649 passed, 2 skipped, 0 failed in 1208.44s (0:20:08)
```

1649 = the 1624 of the P1.2 suite + exactly the 25 new tests, with no regression in any
existing test.

---

## 13. MAIN DB PROTECTION

```
MAIN_DB_SHA_BEFORE = 1c1b2d8538d7a3c52a79a64dec904c69c6ec964b86decbc6508d0d2a438fe522
MAIN_DB_SHA_AFTER  = 1c1b2d8538d7a3c52a79a64dec904c69c6ec964b86decbc6508d0d2a438fe522
MAIN_DB_SIZE       = 64917504 bytes (before and after)
MAIN_DB_MTIME      = 1789877022 (2026-09-20 12:03:42.878312700 +0800, before and after)
MAIN_DB_TOUCHED    = NO
```

No `reset` / `clean` / `restore` / `stash` / `checkout --` / `rebase` / `merge` / `pull` /
`push` was run. **This session touched NO frontend file.** **No migration and no schema change
was made** (see BLOCKERS §1 — that is a deliberate, reported limitation, not an oversight).

### 13.1 Note on the working tree (an observation, not this task's change)

While preparing this report, two FRONTEND files that were NOT modified when this session
started show as modified, with mtimes INSIDE this session's window:

```
frontend/src/types/api.ts                          mtime 2026-09-20 15:30   (+7484/−2708 lines: a regeneration)
frontend/src/features/home/learning-worlds.tsx     mtime 2026-09-20 16:18   (+11/−… lines)
frontend/src/components/layout/app-shell.tsx       mtime 2026-09-20 15:56
frontend/src/routeTree.gen.ts                      mtime 2026-09-20 15:57
```

None of them was opened or edited by this session: every write this session made is in
`backend/`, plus `CLAUDE.md` and report `.md` files. The api-type regeneration at 15:30 in
particular is an `npm run api:generate`-style write, which this session never ran. The likely
explanation is a SECOND concurrent session working on the frontend contract; it is reported
here so the tree state is not mis-attributed. Note also that a frontend regeneration performed
BEFORE this task's endpoints existed will not contain `POST /ai/deep-study`,
`POST /programming/agent/debug`, `GET /review` or `GET /review/summary` — a re-generation is
required before the frontend consumes them (§14).

---

## 14. FRONTEND READINESS

```
STRONG_REASONING_FRONTEND_READY  = YES (with the timeout caveat below)
PROGRAMMING_AGENT_FRONTEND_READY = YES (with the project/streaming caveats below)
UNIFIED_REVIEW_FRONTEND_READY    = YES (with the content-pointer caveat below)
```

* **Deep Study** — the contract is complete and typed (`/openapi.json` declares
  `DeepStudyResponse`, `DeepStudyCitation`, `DeepStudyModelOption`, `DeepStudyUsage`, …) with
  the error answers a client must render: 400 (bad scope/materials), 403 (tier),
  429 (budget), 502 (technical). **Caveat**: it is a single blocking request with no
  streaming and no progress channel — a strong-reasoning answer on a thinking model can take
  tens of seconds, so the client must carry a generous timeout and show its own loading state.
* **Programming Agent** — typed (`AgentDebugResponse` + `AgentStepView`). **Caveats**: (a) a
  standard-I/O exercise with no project yet returns 409 `project_required` — the client should
  route the learner through the exercise page first; (b) the run is a single blocking request
  (no per-step streaming), so a 3-cycle run shows no intermediate output; (c) `steps[]` entries
  are heterogeneous by design (a model step has no `tests`, an execution step has no
  `ai_request_id`), so the client must render optional fields.
* **Unified Review** — typed (`ReviewListResponse`, `ReviewItemView`, `ReviewSummaryResponse`)
  and the `deep_link` values point at route paths the frontend already has. **Caveat**: items
  carry no question text by design; the review page links into the domain page for content.

---

## 15. GATES

```
P1_2_FINAL_SUITE            = 1624 passed / 2 skipped / 0 failed (35:46)
STRONG_REASONING            = PASS (tutor.strong_reasoning; Standard+Advanced; unified lifecycle; typed contract)
DEEP_STUDY                  = PASS (existing FTS/BM25 retrieval; bounded evidence; no vector DB)
CITATION_MODEL              = PASS (shared citation shape; citations only from retrieved+allowed chunks; empty is stated)
PROGRAMMING_AGENT           = PASS (bounded loop over the existing execution backend; advisory; no false learner facts)
AGENT_LIMITS                = PASS (3 iterations / 4 executions / 7 model steps / 240s, all checked before a step)
UNIFIED_REVIEW              = PASS (4 sources, 3 buckets, stored dates only, no prediction fields, user-isolated)
CAPABILITY_INTEGRATION      = PASS (2 capabilities in the ONE tier/pool policy; no new quota system)
USAGE_INTEGRATION           = PASS (one request per model step; reserve→settle/release; deterministic step ids)
EVENTS                      = PASS (5 new ACTIVE families with real producers; review_completed left DEFERRED; §34 respected)
TESTS                       = 25 new tests green; full suite 1649 passed / 2 skipped / 0 failed (20:08)
MAIN_DB_SHA_BEFORE          = 1c1b2d8538d7a3c52a79a64dec904c69c6ec964b86decbc6508d0d2a438fe522
MAIN_DB_SHA_AFTER           = 1c1b2d8538d7a3c52a79a64dec904c69c6ec964b86decbc6508d0d2a438fe522
MAIN_DB_TOUCHED             = NO
STRONG_REASONING_FRONTEND_READY  = YES (blocking call; client timeout caveat)
PROGRAMMING_AGENT_FRONTEND_READY = YES (409 project_required; no per-step streaming)
UNIFIED_REVIEW_FRONTEND_READY    = YES (content rendered by the domain page)
```

---

## 16. BLOCKERS

1. **The agent's per-step trace has no dedicated table, and that is deliberate.** A durable
   per-step table (`programming_agent_runs` / `_steps`) would require a new Alembic revision
   (`20260920_0013`), which would force updating SEVEN other sprints' frozen head-pin
   assertions (`test_s5`, `test_s9`, `test_s6`, `test_s4`, `test_practice_migration`,
   `test_bc7_*`, `test_exam_final_acceptance` all assert `EXPECTED_HEAD == "20260919_0012"`).
   That is a cross-sprint governance change the task did not authorise, so it was NOT done.
   **What exists instead**: one `ai_requests` row per model step (deterministic ids, real
   cost/latency/status) + the code-free per-step trace in the run's canonical events + the
   execution results in the run trace. **What is missing**: the patch TEXT and the final code
   are returned to the caller but NOT persisted server-side (§34 forbids code in an event
   payload, and no other owned store exists). Recommended follow-up: add the table together
   with the 0013 migration and the seven pin updates, as its own authorised step.
2. **Deep Study does not stream.** A single blocking call is the honest v1 (the orchestrator's
   `AIRequestSpec.stream` is `False` and enabling SSE is a separate, cross-cutting change).
   Long answers need frontend patience.
3. **The debug agent runs no autonomous multi-run loop across submissions** — by design. It is
   one bounded workflow over one submission; there is no background worker and no retry across
   sessions.
4. **Exam-space wrong-answer CONTENT resolution on the GLOBAL `/wrong-answers` route still
   materializes by bare primary key** (carried over from the P1.2 report: the exam resolver's
   `_SourceIndex` has no owner check, and that route renders course-namespace states too).
   Out of scope here; still the highest-value security follow-up.
5. **Review carries no question content** (deliberate, see §8): a review page must render the
   stem from the domain page. If a future round wants stems inline, it must go through the
   hardened per-space resolvers, not a new one.
6. **The two new capabilities route through qualification proxies.** `POOL_VERSION` was not
   bumped and no model was re-benchmarked: if a future round wants a real Deep-Study or Agent
   qualification, it replaces the proxy entry and nothing else.
7. `main.py`'s endpoint count is now larger by four routes (three registrations, four paths);
   any document that pins the old count (CLAUDE.md's "351 business endpoints") is stale by
   that amount — reported here rather than silently edited.
