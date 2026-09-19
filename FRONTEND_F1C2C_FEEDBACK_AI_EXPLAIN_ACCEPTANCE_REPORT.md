# FRONTEND_F1C2C Feedback + AI Explain Acceptance Report

Date: 2026-09-18.
Scope: frontend only. No backend file, route, schema, migration or `api.ts` change.

```text
FRONTEND_F1C2C_COMPLETE = YES
FRONTEND_F1C2D_READY    = YES
```

---

## Implemented

- Choice feedback reads the authoritative `correct`, `user_answer`, and `standard_answer` from submit or submitted-attempt `results`, keyed by `question_id`.
- Big questions use `question_type === "big"` and `judge === "self_review"`; they render self-review, submitted answer, and reference only.
- Static `analysis` is rendered only when non-empty and remains distinct from the optional AI explanation.
- AI explanation is an explicit, post-submit-only mutation. Its generated request uses result-owned stem, options, user answer, standard answer, and question type. The mutation has `retry: false`.
- AI response renders `analysis` only. Errors map locally; AI state is keyed by `attempt_id:question_id`, preventing cross-question response bleed.
- The route persists the attempt id in URL search state so a reload retrieves and replays submitted results. AI output intentionally returns to idle on reload.

## Boundaries

- No frontend grading comparison, answer.grade call, wrong-record write, knowledge-status write, provider/model/request-id rendering, or AI auto-call.
- No backend files or migrations changed.

---

# Part 1 — Fixture / route-double VQA (previous pass)

Recorded here only for provenance. **This is NOT the real backend gate** — it intercepts every API
call with `page.route`, so it proves the UI contract against a fixed payload, not against the real
backend.

- `npm run check`: PASS — typecheck, lint, 44 unit/component tests.
- `npm run build`: PASS.
- `tests/e2e/f1c2c-vqa.spec.ts`: PASS — desktop correct/incorrect feedback, submitted reload, big
  self-review, AI success, mobile flow, scoped Axe.
- Screenshots: `%TEMP%/zhixue-f1c2c-vqa/screenshots/`.

---

# Part 2 — REAL AUTHENTICATED BACKEND VQA (this pass)

## 2.1 Environment

| Item | Value |
| --- | --- |
| `BACKEND_VQA_PORT` | **8951** (never 8000; nothing was listening on 8000) |
| `TEMP_DB` | `%TEMP%\f1c2c-real\vqa.db` (disposable, reseeded per run) |
| Backend | real `main:app` served by a harness (`harness_app.py`, outside the repo) |
| Frontend | real Vite dev server, `VITE_API_BASE_URL=http://127.0.0.1:8951` |
| Spec | `frontend/tests/e2e/f1c2c-real-vqa.spec.ts` (no `page.route` anywhere) |
| Result | **5 passed** |

## 2.2 Real authentication

`POST /login` against the real FastAPI app with a real bcrypt-verified account, issuing a real
`auth_sessions` row and a real `ai_session` cookie:

```
login: 200 vqa_student
cookies: [('ai_session', '127.0.0.1', '/')]
```

The browser context carries that cookie into every `apiClient` call (`credentials: 'include'`), and
the spec asserts the cookie is present in the page context before driving the UI. No user object is
injected into frontend code, and no auth is bypassed.

```text
REAL_AUTH_SESSION = PASS
```

## 2.3 Provider double position

The real app is served unmodified. The **only** substitution is the outbound transport, installed by
replacing `ai.orchestrator.default_provider_factory` in the harness process:

```
AIOrchestrator → permission → router → estimate → reserve → [provider double] → cost → settle
                    real        real      real      real        replaced          real    real
```

Everything the task requires to stay real stayed real: the route, auth, capability permission,
usage estimate, reservation, router / qualified-model selection, cost accounting, settlement and
response shaping. The double reports `provider=<routed provider>` and `model=<routed model>`, so the
routed `deepseek / deepseek-flash` pair still flows through real pricing.

No real provider class is constructed and no provider key is read.

```text
PAID_PROVIDER_CALLS = 0
```

## 2.4 Flows verified against the real backend

| Flow | Result |
| --- | --- |
| A — correct choice: real submit → 回答正确 / 你的答案：B / 正确答案：B | PASS |
| A — browser refresh replays the same answer, authoritative result and standard answer | PASS |
| B — incorrect choice: 回答错误 / 你的答案：A / 正确答案：B, identical after refresh | PASS |
| C — big: 自行复盘 / 你的作答 / 参考答案, no 回答正确 / 回答错误 / AI判分 / 得分 | PASS |
| C — refresh reconstructs `question_type = big`, `judge = self_review`, saved answer, reference | PASS |
| D — AI 讲解 issues the real `POST /exam/11408/data_structure/question-analysis` | PASS |
| D — analysis renders inline; no model, no request_id, no provider branding, no auto-call | PASS |
| E — provider failure: local AI error only; grading, answer, reference, static analysis and navigation intact | PASS |
| F — a delayed explanation for question A never renders under question B | PASS |

```text
CHOICE_CORRECT_REAL = PASS              CHOICE_CORRECT_REFRESH_REAL = PASS
CHOICE_INCORRECT_REAL = PASS            CHOICE_INCORRECT_REFRESH_REAL = PASS
BIG_SELF_REVIEW_REAL = PASS             BIG_SELF_REVIEW_REFRESH_REAL = PASS
AI_EXPLAIN_REAL_ROUTE = PASS            AI_EXPLAIN_REAL_SUCCESS = PASS
AI_FAILURE_ISOLATED_REAL = PASS         CROSS_QUESTION_AI_BLEED_REAL = 0
AUTO_RETRY_AI_EXPLAIN = 0
```

Note on `correct === null` for big questions: the client read type does not carry it (the
`Readable<T>` null-only helper behaviour documented in the BC5C report), so the spec does **not**
assert on it. Self-review is verified through `question_type`, `judge`, and the rendered
自行复盘 / 你的作答 / 参考答案 text — which is what the UI actually consumes.

## 2.5 AI input source

The spec captures the **real** request the browser sends and the **real** pre-submit question
transport:

- `GET …/chapter-practice/questions` returns items with **no** `standard_answer` and **no**
  `analysis` (asserted per item);
- `POST …/question-analysis` nonetheless carries `{ standard_answer: 'B', user_answer: 'B',
  question_type: 'choice' }` plus the submitted stem.

Since the pre-submit payload contains no answer at all, the explain request can only be sourced from
post-submit authority — and this holds both right after submit and after a full reload, where the
values come from the replayed attempt detail.

```text
AI_STANDARD_ANSWER_SOURCE = POST_SUBMIT_AUTHORITY
AI_USER_ANSWER_SOURCE     = POST_SUBMIT_AUTHORITY
PRE_SUBMIT_ANSWER_LEAK      = 0
PRE_SUBMIT_EXPLANATION_LEAK = 0
```

## 2.6 Unified billing lifecycle (TEMP DB)

Every AI request produced the real unified accounting chain, with no legacy quota owner:

```
ai_requests   capability=question.explain  service_namespace=exam_prep  user_id=1
              status=settled n=19 · status=released n=8
ai_cost_records   provider=deepseek model=deepseek-flash n=19 (real pricing table)
usage_ledger      exam_prep: reserve 28+ · settle 19 · release 8
usage_budgets     daily + weekly rows for user 1
legacy: ai_usage_logs 0 · user_quota_overrides 0 · ai_question_attempts 0
```

```text
AI_EXPLAIN_REAL_CAPABILITY  = question.explain
AI_EXPLAIN_REAL_AUTH        = PASS (all rows owned by the authenticated user)
LEGACY_EXAM_AI_QUOTA_OWNER  = 0
```

## 2.7 Side effects of the AI call

A controlled probe snapshotted every related table immediately before and after one successful
explain call:

| Gate | Result |
| --- | --- |
| `AI_CHANGED_ATTEMPT` | NO |
| `AI_CHANGED_GRADE` | NO (`exam_question_done_records` unchanged) |
| `AI_CHANGED_WRONG_RECORD` | NO |
| `AI_CHANGED_KNOWLEDGE_STATUS` | NO (`user_knowledge_progress` = 0) |
| `AI_CHANGED_LEARNER_STATE` | NO |

The single write attributable to the AI call is **one `learning_events` row** with
`event_type='ai_called'`, `source_type='ai_request'`, `event_granularity='ACTIVITY_LEVEL'`,
`question_id=NULL`, `correct=NULL`. That is the orchestrator's own required AI-usage audit event
(STEP7H1 §16), not learner state: no item-level record, no correctness, no mastery. The
wrong-answer tables in the temp DB (`exam_wrong_questions` 1, `wrong_answer_states` 1) were created
by **submit** during the audit probe, not by the AI call, which confirms submit still owns them.

## 2.8 No frontend regrading / forbidden writes

Source audit of `frontend/src/features/exam/**`:

- no answer comparison at all — no `toUpperCase` / `toLowerCase`, no
  `user_answer === standard_answer`, no `normalizeAnswer`, no computed `isCorrect`;
- no reference to `answer.grade`, wrong-answer or knowledge-progress endpoints.

Runtime audit: every API path the browser touched during the full desktop flow was recorded and
checked against forbidden patterns (grade / wrong-answer / knowledge-progress / review /
ai-questions / past-paper) — **zero matches** — while asserting that
`/chapter-practice/attempts` and `/question-analysis` really were exercised.

```text
FRONTEND_GRADING_COMPARISON   = 0
ANSWER_GRADE_CALLS            = 0
FRONTEND_WRONG_RECORD_WRITE   = 0
KNOWLEDGE_STATUS_WRITE        = 0
```

## 2.9 Screenshots (real backend, no interception)

`%TEMP%\f1c2c-real\screenshots\`

| File | Viewport |
| --- | --- |
| `real-desktop-choice-correct-feedback.png` | 1440×900 |
| `real-desktop-choice-incorrect-feedback.png` | 1440×900 |
| `real-desktop-choice-ai-explain.png` | 1440×900 |
| `real-desktop-big-self-review.png` | 1440×900 |
| `real-desktop-ai-failure.png` | 1440×900 |
| `real-desktop-question-switch.png` | 1440×900 |
| `real-mobile-choice-feedback.png` | 390×844 |
| `real-mobile-ai-explain.png` | 390×844 |

Each was inspected visually, not only asserted: the real seeded stems/options/reference answer
render, the choice verdict block shows 判定 / 回答正确 / 你的答案：B / 正确答案：B, the big block shows
自行复盘 / 你的作答 / 参考答案 / 题目解析 with no grading words, the AI block shows only the explanation
text, and the failure state shows the local error with the grading block intact.

```text
AXE_VIOLATIONS = 0     (scoped to .cs408-practice, real backend session, both viewports)
CONSOLE_ERRORS = 0     (the controlled 502 probe's resource-load line is excluded by design;
                        no unhandled application error was logged)
```

## 2.10 Tests

| Check | Result |
| --- | --- |
| `frontend/tests/e2e/f1c2c-real-vqa.spec.ts` | 5 passed (real backend) |
| full e2e suite | 16 passed, 8 skipped (all 8 skips are the pre-existing opt-in `EXAM_VQA=1` / `F1C1_VQA_TOKEN` gates) |
| typecheck | PASS |
| lint | PASS |
| unit tests | PASS — 14 files / 44 tests |
| build | PASS |
| backend | **1099 passed / 0 failed** — unchanged baseline, not re-run |

```text
BACKEND_CODE_CHANGED = NO
```

Verified by mtime: outside the new spec file, nothing under `backend/`, `frontend/src/`,
`frontend/package.json`, `migrations/` or `alembic.ini` was modified during this task.

## 2.11 Real database safety

`backend/app.db` is untouched by the whole VQA:

| Measure | Value |
| --- | --- |
| SHA256 | `1c1b2d85…3fe522` — identical to the baseline |
| size | `64917504` — identical |
| mtime | `2026-09-16 21:24:23` — identical to the baseline |
| `PRAGMA integrity_check` / `quick_check` | `ok` |
| table count | 72 |
| `exam_question_bank` / `programming_exercises` / `knowledge_points` | 9333 / 1923 / 32 |
| `exam_practice_attempts` / `exam_wrong_questions` | 0 / 0 |

`backend/app.db-shm` shows a recent mtime, which is expected and harmless: the database is in WAL
mode, so a **read-only** (`?mode=ro`) connection maps the WAL index. `backend/app.db-wal` is 0 bytes
(nothing pending) and `app.db-shm` is gitignored. The database file itself is byte-identical, so:

```text
REAL_APP_DB_MUTATED = NO
```

---

## Final gates

```text
REAL_AUTH_SESSION = PASS                        BACKEND_VQA_PORT = 8951
CHOICE_CORRECT_REAL = PASS                      CHOICE_CORRECT_REFRESH_REAL = PASS
CHOICE_INCORRECT_REAL = PASS                    CHOICE_INCORRECT_REFRESH_REAL = PASS
BIG_SELF_REVIEW_REAL = PASS                     BIG_SELF_REVIEW_REFRESH_REAL = PASS
AI_EXPLAIN_REAL_ROUTE = PASS                    AI_EXPLAIN_REAL_SUCCESS = PASS
AI_EXPLAIN_REAL_CAPABILITY = question.explain   AI_EXPLAIN_REAL_AUTH = PASS
AI_FAILURE_ISOLATED_REAL = PASS

AI_STANDARD_ANSWER_SOURCE = POST_SUBMIT_AUTHORITY
AI_USER_ANSWER_SOURCE     = POST_SUBMIT_AUTHORITY
PRE_SUBMIT_ANSWER_LEAK = 0                      PRE_SUBMIT_EXPLANATION_LEAK = 0

CROSS_QUESTION_AI_BLEED_REAL = 0                AUTO_RETRY_AI_EXPLAIN = 0
PAID_PROVIDER_CALLS = 0                         LEGACY_EXAM_AI_QUOTA_OWNER = 0

FRONTEND_GRADING_COMPARISON = 0                 ANSWER_GRADE_CALLS = 0
FRONTEND_WRONG_RECORD_WRITE = 0                 KNOWLEDGE_STATUS_WRITE = 0

AXE_VIOLATIONS = 0                              CONSOLE_ERRORS = 0
REAL_APP_DB_MUTATED = NO                        BACKEND_CODE_CHANGED = NO

TYPECHECK = PASS   LINT = PASS   UNIT_TESTS = PASS   BUILD = PASS

FRONTEND_F1C2C_COMPLETE = YES
FRONTEND_F1C2D_READY = YES
BLOCKERS = NONE
```

---

## Carried forward (not blockers)

1. **Submitted attempts do not restore the answer *input* on reload.** After a refresh of a
   submitted attempt, `saved_answers` is empty (submit writes `result_json`, not `answers_json`), so
   the choice radio renders unchecked and the big textarea renders empty — while the result block
   correctly shows 你的答案 / 你的作答. The authoritative answer is always visible, so no gate is
   affected, and the inputs can no longer be submitted anyway (the submit button is gone). A small
   targeted follow-up — seeding `reconciledAnswers` from the replayed result's `user_answer` when the
   attempt is `submitted` — would remove the inconsistency. Left unchanged here because this pass is
   acceptance-only and changing answer-source behaviour is a product decision, not a defect fix.

2. **`.practice-navigator` is `display: none` below 40rem**, so on mobile a learner steps between
   questions with 上一题 / 下一题 instead of jumping. This is a declared responsive design decision,
   not a defect; the real-browser mobile flow was driven the way a mobile learner actually would.

3. The `Readable<T>` null-only property behaviour in `openapi-typescript-helpers` (documented in
   `FRONTEND_BC5C_ATTEMPT_RESULT_REPLAY_ACCEPTANCE_REPORT.md`) still strips `correct` from a big
   question's read type. Harmless today; the real VQA asserts on `question_type` / `judge` instead.
