# FRONTEND_BC5B — EXAM `question.explain` OPENAPI CONTRACT CLOSURE
## ACCEPTANCE REPORT

Task: `FRONTEND_BLOCKER_BC5B`
Date: 2026-09-18
Scope: EXAM `question.explain` transport only. No `answer.grade`, no practice grading, no
wrong-record behaviour, no knowledge status, no attempt/session model, no F1C2C UI.

---

## 1. ENDPOINT OWNERSHIP

### QUESTION_EXPLAIN_ENDPOINT_MATRIX

| Item | Value |
|---|---|
| method | `POST` |
| path | `/exam/11408/{subject_key}/question-analysis` |
| handler | `generate_question_analysis` — [backend/main.py:22303](backend/main.py:22303) |
| request shape (before) | `req: dict` → OpenAPI body `{"type":"object","additionalProperties":true,"title":"Req"}` |
| response shape (before) | no `response_model` → OpenAPI `200: {schema: {}}` |
| auth owner | `Depends(get_current_user)` — session cookie `ai_session`; unauthenticated → **401** |
| entitlement owner | `usage.capabilities.check_capability_permission(tier, "question.explain")` |
| usage / budget owner | `usage.service.reserve_credits` → `settle_credits` / `mark_reconciliation_pending` |
| orchestrator call | `learning.spaces.exam_prep.ai.execute_exam_ai(...)` → `AIOrchestrator().execute(...)` — [backend/main.py:22304](backend/main.py:22304) |
| provider access | registry only, via `ai.orchestrator.default_provider_factory` → gateway adapter |

`execute_exam_ai` is reached from exactly **two** call sites in the whole product: this route
(`question.explain`) and `grade_big_answer` (`answer.grade`, out of scope). There is **no other
exam-space `question.explain` endpoint**; the generic `/practice/questions/{id}/ai-explain`
route belongs to the `course_learning` space and was not touched.

**QUESTION_EXPLAIN_ENDPOINT_IDENTIFIED = PASS**

---

## 2. RUNTIME REQUEST (audited, not invented)

Every field was read off the live handler before typing. Nothing was added.

| name | type | required | nullable | meaning |
|---|---|---|---|---|
| `stem` | `str` | no → handler 400 | no | the question text the model explains |
| `options` | `dict[str, str]` | no (default `{}`) | n/a | letter → option text, rendered `A. …` |
| `standard_answer` | `str` | no | no | **caller-supplied** reference answer for prompt context |
| `user_answer` | `str` | no | no | **caller-supplied** learner answer for prompt context |
| `question_type` | `str` | no | no | defaults to `选择题` |
| `context` | `str` | no | no | accepted for historical callers; **currently unused** by the prompt |

`stem` is declared Optional on purpose so an omitted stem keeps the handler's own
`400 "stem is required"` instead of turning into a `422` — the same deliberate choice already
made for `ExamPracticeAttemptCreateRequest.question_ids` ([backend/main.py:21563](backend/main.py:21563)).

**Runtime equivalence:** unknown extra keys are still ignored (`extra="ignore"`), so the
pre-existing callers — including `tests/test_gateway_migration.py` and
`tests/test_exam_prep_namespace.py`, which send exactly the five known fields — are unchanged.

---

## 3. RUNTIME RESPONSE

Observed on the live route (probe A, temp DB, deterministic provider double):

```json
{"analysis": "...", "generated_at": "2026-09-18T05:27:40.759943Z",
 "model": "deepseek-flash", "request_id": "9b6c8b56b2c046bbbb3199098d7edc27"}
```

| name | type | meaning |
|---|---|---|
| `analysis` | `str` | the model's explanation — **the only field F1C2C renders** |
| `generated_at` | `str \| None` | server timestamp of the call |
| `model` | `str \| None` | AIRequest identity of the billed call; **not** a provider chooser |
| `request_id` | `str` | unified `ai_requests.request_id` |

`model` / `request_id` pre-date BC5B and stay (removing them would be an unrequested contract
break). They are documented in the model docstring as **not** provider branding — §18 forbids a
provider/model selector, and none was added.

**No `standard_answer`, no `analysis` (static), no provider registry is exposed.**

---

## 4. PRACTICE-CONTEXT SECURITY  ← the important finding

### 4.1 The endpoint is stateless and answer-blind

The handler reads **no question row**. It issues no query against `exam_question_bank`,
takes no `question_id`, and resolves nothing from storage. Everything it feeds the model is
caller-supplied text.

Proven at runtime:

```
POST /exam/11408/data_structure/question-analysis  {"question_id": 42, "attempt_id": 1}
→ 400 {"detail":"stem is required"}
```

The identities are silently dropped; the request is refused before any provider call.

### 4.2 Trust boundary — reported explicitly, not blessed

> **`standard_answer` is frontend-supplied and the backend treats it as prompt truth.**

This is a **generic question-explanation endpoint**, not an answer-aware post-submit endpoint
with server-side authority. The consequence for F1C2C:

* the backend cannot be tricked into disclosing a stored answer, because it never had one;
* but it also **cannot prove post-submit state** — the UI is the only party that knows the
  attempt has been submitted. A caller who already holds the standard answer gains nothing;
  a caller who does not hold it cannot get it from this route.

This is recorded as a known limitation rather than silently accepted as a security property.

### 4.3 PRACTICE_CONTEXT_LIMITATION

```
PRACTICE_CONTEXT_BINDING = NONE (caller-supplied question text; no question_id, no attempt_id,
                                 no server-side ownership or submitted-state proof)
PRACTICE_CONTEXT_LIMITATION = the endpoint cannot be bound to attempt_id/question_id, and the
                              backend cannot prove "this user owns this attempt" or "this
                              question was submitted". Per §8 no new practice-session table
                              and no new endpoint were added to manufacture a binding.
```

The practice attempt itself **does** gate post-submit correctly, and that gate is intact:
`GET /exam/11408/{subject_key}/chapter-practice/attempts/{id}` strips `standard_answer` and
`analysis` while `status != "submitted"` ([backend/main.py:21926](backend/main.py:21926)).
Verified live: the pre-submit question payload contains neither key; the post-submit result
payload contains both. **Post-submit gating lives in the attempt route, which is where it
belongs; the explain route is stateless by design.**

### 4.4 Pre-submit probes (§24)

| Probe | Result |
|---|---|
| pre-submit attempt view carries `standard_answer` / `analysis` | **NO** (stripped) |
| explain route accepts `question_id` / `attempt_id` to fetch an answer | **NO** — 400, no provider call |
| explain 200 body contains a stored answer field | **NO** — body is exactly `{analysis, generated_at, model, request_id}` |
| seeded a bank row with `standard_answer="CONFIDENTIAL-REFERENCE-KEY"`, then called explain with only stem+options | the secret string does **not** appear anywhere in the response; the static `analysis` ("静态解析") does not ride along either |

**QUESTION_EXPLAIN_PRE_SUBMIT_ALLOWED = YES**
— the route is callable at any time (it is a generic explainer). It is *not* an
answer-disclosure gate, because it holds no answer to disclose.

**AI_EXPLAIN_PRE_SUBMIT_ANSWER_LEAK = 0**

**F1C2C obligation (handoff):** call this route **only after** the attempt is submitted, using
the `standard_answer` the submit response returned. The backend will not enforce this.

---

## 5. CAPABILITY / AUTHORIZATION

```
route → execute_exam_ai(db, user, "question.explain", […] )
      → AIOrchestrator.execute → check_capability_permission(tier, capability)
```

`question.explain` is in the **free**, standard **and** advanced tiers
([backend/usage/capabilities.py:24](backend/usage/capabilities.py:24)), so a tier-based 403 is
**unreachable through this route**. The refusal machinery is nonetheless live and was exercised
deterministically by substituting the orchestrator boundary:

| scenario | status | provider calls |
|---|---|---|
| allowed (free tier, real path) | 200 | 1 |
| `permission_denied` / `tier_not_permitted` | **403** `AI capability unavailable` | 0 |
| `budget_reserve_failed` | **429** | 0 |
| `no_qualified_model_available` | **502** | 0 |
| provider `GatewayError` | **502** `AI capability unavailable` | 1 (failed) |
| unauthenticated | **401** `请先登录` | 0 |
| missing/empty stem | **400** `stem is required` | 0 |
| wrong field type | **422** (normalized validation message) | 0 |

`QUESTION_EXPLAIN_AUTHORIZATION = PASS` (capability-permission driven; the frontend must not
infer entitlement from a membership name).

---

## 6. USAGE ACCOUNTING

Unified lifecycle, confirmed row-by-row:

```
estimate → reserve → execute → actual → settle
```

Two live calls produced, per request:

```
capability=question.explain status=settled ns=exam_prep reserved=1 actual=1
  ledger(3): reserve:1@reserve:<rid>:daily
             reserve:1@reserve:<rid>:weekly
             settle:1@settle:<rid>
  ai_cost_records=1
```

The two `reserve` rows are the **daily and weekly period buckets** — two distinct budgets, each
debited once — not a duplicated charge. One `AICostRecord` and one `settle` per request.

* **DOUBLE_BILLING = 0** — 1 request_id → 1 reserve-lifecycle → 1 cost record → 1 settle, all
  under `service_namespace = exam_prep`.
* **LEGACY_EXAM_AI_QUOTA_OWNER = 0** — `check_exam_408_usage_limit` is not referenced by this
  route, and its only remaining callers anywhere are two direct unit tests of the legacy helper
  itself. The route uses neither it nor `check_usage_limit`.

**No accounting change was made** — the audit found no violation.

---

## 7. SIDE-EFFECT AUDIT

Snapshot before/after the explain call, on a real submitted chapter-practice attempt:

| state | changed |
|---|---|
| `exam_practice_attempts` (status, counts, accuracy, result_json, answers_json, submitted_at) | **NO** |
| `exam_wrong_questions` (status, user_answer, mastered, review_count, snapshots) | **NO** |
| `exam_question_done_records` | **NO** |
| `exam_question_bank` (stem, standard_answer, **analysis**) | **NO** — static analysis untouched |
| `user_knowledge_progress` (status, mastery, review interval) | **NO** |
| `knowledge_progress_events` | **NO** |
| `learning_records` | **NO** |
| `model_predictions` (learner state) | **NO** |
| unified AI accounting rows | +1 request, +1 cost record (expected) |

```
QUESTION_EXPLAIN_CAN_CHANGE_GRADE = NO
QUESTION_EXPLAIN_CAN_WRITE_WRONG_RECORD = NO
QUESTION_EXPLAIN_CAN_WRITE_KNOWLEDGE_STATUS = NO
QUESTION_EXPLAIN_CAN_RESOLVE_WRONG = NO
QUESTION_EXPLAIN_CAN_WRITE_LEARNER_STATE = NO
QUESTION_EXPLAIN_CAN_MODIFY_ATTEMPT = NO
```

---

## 8. STATIC EXPLANATION vs AI  (§15)

AI output is **not persisted anywhere**. The docstring's "Not persisted" claim was verified:
the response goes straight to the caller, and `exam_question_bank.analysis` is byte-identical
after the call (asserted in `test_static_bank_analysis_is_never_overwritten`). There is **no
cache** of AI output on this route, so static analysis and AI explanation cannot collide.

---

## 9. FAILURE ISOLATION

Provider `timeout` injected at the provider factory:

```
POST … → 502 {"detail": "AI capability unavailable"}
ai_requests: capability=question.explain status=reconciliation_pending
             error_category=cost_reconciliation_pending
```

The attempt stays `submitted` with its grade, wrong records and static analysis intact; only
the AI explanation area is affected. The reservation is deliberately **not** silently released
on a provider failure — it is parked as `reconciliation_pending` for the reconcile worker,
which is the correct conservative choice (the provider may have billed).

**AI_EXPLAIN_FAILURE_ISOLATED = PASS**

---

## 10. RETRY SEMANTICS  (§17)

```
QUESTION_EXPLAIN_RETRY_SEMANTICS = NEW BILLABLE CALL EVERY TIME (no cache, no idempotency key)
```

Three identical requests produced three distinct `request_id`s and three provider calls. There
is no `request_id` parameter on the contract, so a client cannot dedupe. **F1C2C must not
auto-retry** — a retry costs real credits.

---

## 11. OPENAPI  (§19)

Before → after, from the live spec served on a free non-8000 port (temp DB copy):

| | before | after |
|---|---|---|
| request body | `{"type":"object","additionalProperties":true,"title":"Req"}` | `$ref → ExamQuestionAnalysisRequest` |
| 200 schema | `{}` | `$ref → ExamQuestionAnalysisResponse` |

```
QUESTION_EXPLAIN_REQUEST_UNKNOWN = 0
QUESTION_EXPLAIN_SUCCESS_UNKNOWN = 0
```

No new endpoint, route, capability or model was introduced. Path set is unchanged (323 → 323);
the only spec delta is this one operation.

---

## 12. GENERATED TYPESCRIPT  (§20 / §21)

Regenerated with the repo's own tool (`openapi-typescript 7.13.0`) from a spec served on
**port 8948** with an explicit temp `DATABASE_URL`. `localhost:8000` was **not** used;
`package.json` was **not** changed; `api.ts` was **not** hand-edited.

The `api.ts` diff is **exactly 59 lines**, all of them this operation plus the two new schemas
— measured against the file's own pre-regeneration state, so it carries no unrelated drift:

```
+   ExamQuestionAnalysisRequest: { stem?, options?, standard_answer?, user_answer?,
+                                 question_type?, context? }
+   ExamQuestionAnalysisResponse: { analysis: string; generated_at: string | null;
+                                  model: string | null; request_id: string }
-   "application/json": { [key: string]: unknown; }     →  …["ExamQuestionAnalysisRequest"]
-   "application/json": unknown;                          →  …["ExamQuestionAnalysisResponse"]
```

**Compile-level proof** — `frontend/src/test/question-explain-contract.test.ts` builds the
request from the **generated** types, reads `analysis` off the generated 200, and asserts the
contract exposes no `model` / `provider` request field. Kept as a permanent regression test
(not a throwaway probe). Non-vacuity was demonstrated by temporarily restoring the pre-typing
`api.ts`: typecheck then fails with `Property 'analysis' does not exist on type 'unknown'`.

```
HAND_WRITTEN_FRONTEND_TRANSPORT_DTO = 0
```

---

## 13. RUNTIME QA  (§22 / §23)

The real paid provider was **never called**. DeepSeek is configured with a live key in this
environment, so the valid path was exercised through the app's own ASGI client with the
outbound call replaced at the **orchestrator provider factory** — the double sits below the
real permission / router / pool / estimate / reserve / settle lifecycle, which all ran for real.

| Probe | Method | Result |
|---|---|---|
| A allowed | TestClient + provider double, real attempt | 200, `question.explain`, `stream=false`, ns `exam_prep` |
| B denial | orchestrator boundary substituted | 403, 0 provider calls |
| C budget | orchestrator boundary substituted | 429, 0 provider calls |
| D provider failure | factory raises `GatewayError` | 502, attempt/grade intact |
| E real HTTP | live uvicorn :8948, temp DB | 401 / 400 / 422 verified on the wire |
| F practice context | real create → answer → submit → explain | explanation available; nothing else changed |
| G pre-submit | bank row seeded with a secret answer string | no leak in the response body |

§23 practice-context flow executed end to end against a **real** temp practice attempt: create
attempt → submit a wrong choice answer → invoke `question.explain` with the submit response's
own fields. Explanation returned; grade, wrong record, knowledge status, learner state,
attempt row and static analysis all unchanged.

---

## 14. TESTS  (§26)

New: [backend/tests/test_bc5b_question_explain_contract.py](backend/tests/test_bc5b_question_explain_contract.py) — **26 tests**, mapping to the
20 required points (1–2 OpenAPI concrete, 3–4 generated-TS source, 5–6 orchestrator+capability,
7 zero direct provider, 8 entitlement denial, 9 budget rejection, 10–14 grade/wrong/knowledge/
learner/attempt/static unchanged, 15 failure isolation, 16 post-submit practice context,
17 pre-submit leak = 0, 18 no double billing, 19 retry semantics, 20 runtime equivalence),
plus 401/400/422 semantics and "no legacy quota owner".

New: [frontend/src/test/question-explain-contract.test.ts](frontend/src/test/question-explain-contract.test.ts) — 4 compile-level contract tests.

---

## 15. DB SAFETY  (§27)

`backend/app.db` — read-only throughout (all temp work used a **copy** with an explicit
`DATABASE_URL`):

| | before | after |
|---|---|---|
| SHA256 | `1c1b2d85…438fe522` | `1c1b2d85…438fe522` |
| mtime | `1789565063.8964841` | `1789565063.8964841` |
| size | `64917504` | `64917504` |
| `PRAGMA integrity_check` | `ok` | `ok` |
| table count | 72 | 72 |
| `exam_question_bank` | 9333 | 9333 |
| `programming_exercises` | 1923 | 1923 |
| `knowledge_points` | 32 | 32 |

**REAL_APP_DB_MUTATED = NO**
**DB_SCHEMA_CHANGED = NO**
**MIGRATION_ADDED = NO** — no model, table, column, index or Alembic revision changed.

---

## 16. FILES CHANGED

| file | change |
|---|---|
| [backend/main.py](backend/main.py) | + `ExamQuestionAnalysisRequest`, + `ExamQuestionAnalysisResponse`; `generate_question_analysis` now takes the typed model and declares `response_model`. Handler logic otherwise byte-identical. |
| [frontend/src/types/api.ts](frontend/src/types/api.ts) | regenerated (59-line BC5B delta) |
| [backend/tests/test_bc5b_question_explain_contract.py](backend/tests/test_bc5b_question_explain_contract.py) | new — 26 tests |
| [frontend/src/test/question-explain-contract.test.ts](frontend/src/test/question-explain-contract.test.ts) | new — 4 compile-level tests |

Untouched, as required: `answer.grade`, practice grading, wrong-record flow, knowledge status,
attempt/session model, model pool, router, membership tiers, Usage Budget semantics, `schemas.py`,
`migrations/`, `package.json`.

---

## 17. GATES

```
QUESTION_EXPLAIN_ENDPOINT_IDENTIFIED = PASS
QUESTION_EXPLAIN_ENDPOINT            = POST /exam/11408/{subject_key}/question-analysis
QUESTION_EXPLAIN_TRANSPORT           = JSON

REQUEST_MODEL  = ExamQuestionAnalysisRequest
RESPONSE_MODEL = ExamQuestionAnalysisResponse

QUESTION_EXPLAIN_REQUEST_TYPED  = PASS
QUESTION_EXPLAIN_RESPONSE_TYPED = PASS

QUESTION_EXPLAIN_REQUEST_UNKNOWN = 0
QUESTION_EXPLAIN_SUCCESS_UNKNOWN = 0

DIRECT_PROVIDER_CALLS_IN_EXAM_QUESTION_EXPLAIN = 0

CAPABILITY_USED              = question.explain
QUESTION_EXPLAIN_AUTHORIZATION = PASS

DOUBLE_BILLING               = 0
LEGACY_EXAM_AI_QUOTA_OWNER   = 0

QUESTION_EXPLAIN_CAN_CHANGE_GRADE            = NO
QUESTION_EXPLAIN_CAN_WRITE_WRONG_RECORD      = NO
QUESTION_EXPLAIN_CAN_WRITE_KNOWLEDGE_STATUS  = NO
QUESTION_EXPLAIN_CAN_RESOLVE_WRONG           = NO
QUESTION_EXPLAIN_CAN_WRITE_LEARNER_STATE     = NO
QUESTION_EXPLAIN_CAN_MODIFY_ATTEMPT          = NO

AI_EXPLAIN_FAILURE_ISOLATED      = PASS
AI_EXPLAIN_PRE_SUBMIT_ANSWER_LEAK = 0
QUESTION_EXPLAIN_PRE_SUBMIT_ALLOWED = YES (generic explainer; holds no answer to disclose)

HAND_WRITTEN_FRONTEND_TRANSPORT_DTO = 0

DB_SCHEMA_CHANGED  = NO
MIGRATION_ADDED    = NO
REAL_APP_DB_MUTATED = NO

FULL_BACKEND_TESTS    = PASS (1075 passed / 0 failed; baseline 1049 + 26 new)
FRONTEND_TYPECHECK    = PASS
FRONTEND_LINT         = PASS
FRONTEND_UNIT_TESTS   = PASS (34 passed / 13 files)
FRONTEND_BUILD        = PASS

F1C2C_BACKEND_CONTRACT_READY = YES
```

---

## 18. BLOCKERS / HANDOFF NOTES

No blocker prevents F1C2C from building on this contract. Three obligations pass to the frontend:

1. **Call it only post-submit.** The backend cannot enforce this; the route is a stateless
   generic explainer and will answer at any time. Use the `standard_answer` returned by
   `POST …/chapter-practice/attempts/{id}/submit`.
2. **Do not auto-retry.** Every call is a fresh billed request (`question.explain`, real
   credits). No cache, no idempotency key on the contract.
3. **Render `analysis` only.** `model` / `request_id` are AIRequest identity, not provider
   branding; §18 forbids surfacing a model/provider chooser.

Informational: `context` is accepted but unused by the prompt — the frontend may still send it,
but must not rely on it changing the explanation.

