# FRONTEND_F1C2D Practice Session Acceptance Report

Date: 2026-09-18.
Final real authenticated acceptance after the F1C2D-R1 defect closure.

```text
FRONTEND_F1C2D_COMPLETE = YES
CHAPTER_PRACTICE_WORKSPACE_FROZEN = YES
BLOCKERS = NONE
```

Revision validated (SHA256 prefix):

| File | Hash |
| --- | --- |
| `backend/main.py` | `96a9338e89d92762` |
| `frontend/src/features/exam/components/cs408-practice-workspace.tsx` | `32b3762c74bd103b` |
| `frontend/src/features/exam/components/cs408-practice-workspace.css` | `3c02830bdd02011b` |
| `frontend/src/types/api.ts` | `9755af1d7dc67a5d` |

Product source was not modified by this pass. The only files written are two Playwright specs
(`f1c2d-real-vqa.spec.ts` — corrected assertions, `f1c2d-supplement-real.spec.ts` — new) and this
report. The VQA harness (`seed.py`, `harness_app.py`) lives outside the repository in `%TEMP%`.

---

# Part A — Deterministic frontend QA

| Check | Result |
| --- | --- |
| `npm run typecheck` | **PASS** |
| `npm run lint` | **PASS** |
| `npm run test:run` | **PASS** — 14 files / **46 tests** |
| `npm run build` | **PASS** |

Playwright, whole suite: **24 passed / 1 failed / 8 skipped**.

* The 8 skips are the pre-existing opt-in gates (`EXAM_VQA=1`, `F1C1_VQA_TOKEN`).
* The 1 failure is environmental only: `f1c2c-real-vqa.spec.ts` drives the browser through the Vite
  dev server while its own API calls target port **8951**. This pass requires Vite to point at
  **8952** for the F1C2D acceptance, so that spec sees a different database than the browser. It is
  unrelated to F1C2D and passed in its own pass on its own port.
* **The F1C2B and F1C2C mocked specs — the five that the pre-R1 build regressed — all pass again.**

---

# Part B — FINAL REAL AUTHENTICATED ACCEPTANCE AFTER R1

This is the real acceptance: a real browser talking to the real FastAPI app, real authentication,
real practice persistence, a disposable TEMP database and no intercepted practice transport.

| Item | Value |
| --- | --- |
| `BACKEND_VQA_PORT` | **8952** (non-8000; 5173/8000 verified free) |
| `TEMP_DB` | `%TEMP%\f1c2d-real\vqa.db` (disposable, reseeded per run) |
| Backend | real `main:app` served by `harness_app.py` (outside the repo) |
| Frontend | real Vite dev server, `VITE_API_BASE_URL=http://127.0.0.1:8952` |
| Provider double | swapped below the orchestrator boundary; **call log stayed empty all pass** |
| Real suite | `f1c2d-real-vqa.spec.ts` — **9/9 passed** |
| Supplement | `f1c2d-supplement-real.spec.ts` — **4/4 passed** |

## 1. Real authentication

`POST /login` against the real app with a real bcrypt-verified account issues a real `auth_sessions`
row and a real `ai_session` cookie; the spec asserts the cookie exists in the page context before
driving the UI.

```text
REAL_AUTH_SESSION = PASS
```

## 2. Mixed attempt and authoritative summary

One real attempt carries all four classes. Raw results read straight out of the persisted attempt:

```
RAW_RESULT_MATRIX  (mixed attempt id 55)
  qid 1  choice  user_answer='B'   server_correct=True   -> CHOICE CORRECT
  qid 2  choice  user_answer='A'   server_correct=False  -> CHOICE INCORRECT
  qid 3  choice  user_answer=''    server_correct=False  -> UNANSWERED
  qid 4  big     user_answer='…'   judge=self_review      -> BIG SELF REVIEW

EXPECTED_SUMMARY  (computed independently in the harness from the raw results — never via the
                   component's helper)
  共 4 题 | 已作答 3 · 答对 1 · 答错 1 · 自行复盘 1 · 未作答 1 | 自动判分题正确率 50%

RENDERED_SUMMARY
  共 4 题 | 已作答 3 · 答对 1 · 答错 1 · 自行复盘 1 · 未作答 1 | 自动判分题正确率 50%

  answered == correct + incorrect + self_review  ->  True (3 == 3)
  unanswered is a separate bucket                ->  未作答 1
```

```text
SUMMARY_FROM_AUTHORITATIVE_RESULTS = PASS
ACCURACY_GRADED_ONLY = PASS            (denominator = graded choices = 2 -> 50%;
                                        a big-only attempt renders 本次没有自动判分题, no fake 0%)
```

## 3. wrong_count exclusion — proven at runtime

```
backend aggregate on that same attempt:  correct_count=1  wrong_count=2  accuracy=33.3
UI summary:                                                       答错 1           50%
```

The blank choice persists `server_correct=False`, so the backend's own aggregate folds it into
`wrong_count`; the UI applies the `user_answer !== ""` guard first and never reads
`attempt.wrong_count` (source audit: `wrong_count` appears only as test fixture data, never in
`src/`).

```text
BACKEND_WRONG_COUNT_USED_FOR_UI_INCORRECT = NO
UNANSWERED_EQUALS_INCORRECT = NO
```

## 4. Submit → summary → review → summary (R1 regression check)

```
submit            -> Summary is the default view                     SUBMITTED_SUMMARY_DEFAULT_REAL = PASS
查看本次题目       -> the question desk becomes visible                VIEW_SUBMITTED_QUESTIONS_REAL   = PASS
本次练习总结       -> returns to the Summary, attempt untouched        RETURN_TO_SUMMARY_REAL          = PASS
refresh           -> submitted attempt reloads to Summary, identical
                     counts, and 查看本次题目 still works               SESSION_SUMMARY_REFRESH_REAL    = PASS
```

The R1 fix separates UI view mode from persisted status: `viewMode` state defaults from
`isSubmittedAttempt` but is overridable, so `attempt.status == 'submitted'` no longer forces the
summary. Verified in both directions, right after submit and after a reload.

```text
SUBMITTED_VIEW_MODE_REAL = PASS
```

### Read-only answer rehydration

In the submitted review, the choice radio carrying the authoritative `user_answer` is
`checked` **and** `disabled`, the big question's textarea holds the authoritative text **and** is
`disabled`, and the submit button is absent (`toHaveCount(0)`). The values come from
`results[].user_answer`, not from draft state.

```text
SUBMITTED_INPUT_REHYDRATION_REAL = PASS
```

## 5. Unanswered confirmation

Clicking 提交本章答案 with a blank question raises `role="alertdialog"` reading
还有 1 题未作答，仍要提交本次练习吗？ with 继续作答 / 仍然提交; 继续作答 dismisses without submitting;
ordinary 上一题 / 下一题 raise nothing.

```text
UNANSWERED_CONFIRMATION_REAL = PASS
```

## 6. Retry subset — attempt defines the desk question set

```
ORIGINAL_ATTEMPT_ID       = 55 (submitted, 4 results, untouched afterwards)
EXPECTED_RETRY_IDS        = [2]        (answered AND server correct === false)
ACTUAL_RETRY_ATTEMPT_IDS  = [2]        (from GET …/attempts/{id} -> questions[].id)
RETRY_ATTEMPT_QUESTION_IDS = [2]
RENDERED_RETRY_QUESTION_IDS = [2]      (from the live DOM)

blank (qid 3) absent · big (qid 4) absent · correct choice (qid 1) absent
navigator shows 本次 1 题 with a single entry; 第 2/3/4 题 buttons have count 0
```

The retry attempt's own question set now drives what the desk renders, so the pre-R1 phantom
rendering is gone.

```text
RETRY_CREATES_NEW_ATTEMPT_REAL = PASS
RETRY_UNANSWERED_INCLUDED = NO   RETRY_BIG_INCLUDED = NO   RETRY_CORRECT_INCLUDED = NO
ATTEMPT_DEFINES_RENDERED_QUESTION_SET = PASS
PHANTOM_QUESTION_RENDERING_REAL = 0      PHANTOM_ANSWER_SURFACE = 0
```

再做一遍本章 separately creates a fresh attempt over the full chapter set `[1,2,3,4]` while the
previous attempt stays `submitted` with 4 results; 返回章节 keeps `module=data_structure`, drops
`chapter`, and the chapter link carries the canonical code `1` (not an index or a Chinese title).

```text
NEW_CHAPTER_ATTEMPT_REAL = PASS      RETURN_CHAPTER_REAL = PASS
```

## 7. Contrast and answered-state semantics

Measured in the real browser (WCAG 2.x, element text against its nearest opaque background):

| Target | Foreground / background | Ratio | Required |
| --- | --- | --- | --- |
| Summary 返回章节 link | `#1d4ed8` / `#f5f4ef` | **6.09** | ≥ 4.5 |
| Summary facts text | `#172033` / `#f5f4ef` | 14.79 | ≥ 4.5 |
| Summary heading | `#0c1730` / `#f5f4ef` | 16.17 | ≥ 4.5 |
| Answered navigator button (answered, not current) | `#1d4ed8` / `#e8e5da` | **5.31** | ≥ 4.5 |

The answered state no longer borrows success semantics: its colour is `--color-primary-hover`
(`#1d4ed8`) with an ink underline, explicitly **not** `--color-success` (`#16a34a`).

```text
ANSWERED_STATE_USES_SUCCESS_SEMANTICS = NO
ANSWERED_NAV_TEXT_CONTRAST = 5.31        SUMMARY_LINK_TEXT_CONTRAST = 6.09
```

## 8. Accessibility and console

axe, scoped to `.cs408-practice`, on real pages:

| Page | Violations |
| --- | --- |
| desktop Session Summary | 0 |
| desktop submitted review | 0 |
| desktop unanswered confirmation | 0 |
| mobile Session Summary | 0 |

Plus: mobile summary has no horizontal overflow (scrollWidth − clientWidth = 0), the confirmation
exposes an accessible name and both actions are real buttons, headings are semantic (`h2` per
region with `aria-labelledby`), and console stayed clean during the successful real flows.

```text
AXE_VIOLATIONS = 0        CONSOLE_ERRORS = 0
```

## 9. Forbidden calls

Source audit of `frontend/src/features/exam/**` finds no `answer.grade`, no wrong-answer or
knowledge-progress endpoint, and no session-summary/planner call; the only write calls are the
practice lifecycle itself (create / save / submit attempt, profile, question-analysis, study-plan).
Runtime: the provider-double call log is absent (0 calls) and the TEMP database shows
`ai_requests = 0`, `ai_cost_records = 0`, `usage_ledger = 0`, `user_knowledge_progress = 0`.

```text
SESSION_SUMMARY_AI_CALLS = 0     ANSWER_GRADE_CALLS = 0
FRONTEND_WRONG_RECORD_WRITE = 0  KNOWLEDGE_STATUS_WRITE = 0
QUESTION_INDEX_AS_IDENTITY = NO  FRONTEND_GRADING_COMPARISON = 0
```

## 10. Real screenshots

`%TEMP%\f1c2d-real\screenshots\` — all seven required captures, inspected visually.

| File | Viewport |
| --- | --- |
| `real-desktop-session-summary.png` | 1440×900 |
| `real-desktop-session-summary-mixed.png` | 1440×900 |
| `real-desktop-submitted-review.png` | 1440×900 |
| `real-desktop-retry-subset.png` | 1440×900 |
| `real-desktop-unanswered-confirm.png` | 1440×900 |
| `real-mobile-session-summary.png` | 390×844 |
| `real-mobile-unanswered-confirm.png` | 390×844 |

**DESKTOP_VISUAL_QA = PASS.** The summary now reads as a completed Technical Exam Desk sheet: it
carries the same `border-top: 2px solid var(--color-lab-ink)` rule, lab-paper panel tint and
`clamp()` type scale as the header, question and result blocks; its facts sit between hairline rules
with the lead fact in primary-bold; actions are the shared Button component and 返回章节 is a proper
underlined link. It is not a KPI dashboard, card grid, analytics screen, success modal or unstyled
HTML. The submitted review and the retry subset read as the same desk.

**MOBILE_VISUAL_QA = PASS.** Summary and confirmation wrap correctly at 390×844, no horizontal
overflow, and the navigator's `display: none` below 40rem is the accepted behaviour (mobile steps
with 上一题 / 下一题).

## 11. Database safety

| Measure | Value |
| --- | --- |
| SHA256 | `1c1b2d85…3fe522` — identical to baseline |
| size | `64917504` — identical |
| mtime | `2026-09-16 21:24:23` — identical |
| `integrity_check` / `quick_check` | `ok` / `ok` |
| table count | 72 |
| protected counts | `exam_question_bank` 9333, `programming_exercises` 1923, `knowledge_points` 32 |
| `exam_practice_attempts` / `exam_wrong_questions` | 0 / 0 |
| `app.db-wal` | **0 bytes** — no pending durable write |

```text
REAL_APP_DB_MUTATED = NO
BACKEND_CODE_CHANGED = NO        FRONTEND_CODE_CHANGED = NO        GENERATED_API_CHANGED = NO
```

Verified by mtime: `backend/main.py` 14:00 and `frontend/src/types/api.ts` 14:05 predate this pass;
the component and CSS carry the 19:46/19:48 timestamps of the R1 fix, also before this pass.

## 12. Harness correction (no product change)

The prepared suite's test C asserted the question-1 radio immediately after 查看本次题目. The desk
resumes at the **last-viewed** question (it was left on the big question by the shared setup), so the
radio was legitimately not in the DOM — the failure text was `element(s) not found`, and the captured
page snapshot showed question 4/4 correctly rendered with the big answer restored and disabled. That
is a gap in the test, not a product defect, so the fix was applied in the harness only: it now steps
to 第 1 题 the same way its own post-reload block already did, and additionally asserts the big
question's rehydration (`toHaveValue` + `toBeDisabled`), which the gate requires and the prepared
version did not check.

---

# Appendix — pre-R1 defects (provenance)

For the record, the previous pass on the pre-R1 revision found these, all now closed:

| Defect | Symptom | Closed by |
| --- | --- | --- |
| F1C2D-1 | `status === 'submitted'` permanently pinned the summary; question review and per-question result marks unreachable. Regressed five previously-green F1C2B/F1C2C tests. | `viewMode` state defaulting from, but overriding, the persisted status |
| F1C2D-2a | `.practice-summary` had no CSS rule; the 返回章节 link kept the default `#2563eb` on `#e8e5da` = 4.09:1 | `.practice-summary` styled as part of the desk; link uses `--color-primary-hover` = 6.09:1 |
| F1C2D-2b | `.practice-navigator button.is-answered` used `--color-success` `#16a34a` on `#e8e5da` = 2.61:1 (desktop only) | answered state uses `--color-primary-hover` + ink underline = 5.31:1 |
| F1C2D-3 | A retry attempt holding `[2]` still rendered the whole chapter; answers to the other three were silently dropped at submit | the desk renders the attempt's own question set |

---

# Final gates

```text
REAL_AUTH_SESSION = PASS

SUBMITTED_SUMMARY_DEFAULT_REAL = PASS          SUBMITTED_VIEW_MODE_REAL = PASS
VIEW_SUBMITTED_QUESTIONS_REAL = PASS           RETURN_TO_SUMMARY_REAL = PASS
SUBMITTED_INPUT_REHYDRATION_REAL = PASS

UNANSWERED_CONFIRMATION_REAL = PASS            UNANSWERED_EQUALS_INCORRECT = NO

SUMMARY_FROM_AUTHORITATIVE_RESULTS = PASS      SESSION_SUMMARY_REFRESH_REAL = PASS
ACCURACY_GRADED_ONLY = PASS

BACKEND_WRONG_COUNT_USED_FOR_UI_INCORRECT = NO

RETRY_CREATES_NEW_ATTEMPT_REAL = PASS
RETRY_UNANSWERED_INCLUDED = NO   RETRY_BIG_INCLUDED = NO   RETRY_CORRECT_INCLUDED = NO

ATTEMPT_DEFINES_RENDERED_QUESTION_SET = PASS
PHANTOM_QUESTION_RENDERING_REAL = 0            PHANTOM_ANSWER_SURFACE = 0

NEW_CHAPTER_ATTEMPT_REAL = PASS                RETURN_CHAPTER_REAL = PASS

ANSWERED_STATE_USES_SUCCESS_SEMANTICS = NO
ANSWERED_NAV_TEXT_CONTRAST = 5.31              SUMMARY_LINK_TEXT_CONTRAST = 6.09

SUMMARY_TECHNICAL_EXAM_DESK_REAL = PASS        CONFIRMATION_TECHNICAL_EXAM_DESK_REAL = PASS
SUMMARY_QUESTION_CONTROL_LEAK = NO

QUESTION_INDEX_AS_IDENTITY = NO                FRONTEND_GRADING_COMPARISON = 0

SESSION_SUMMARY_AI_CALLS = 0                   ANSWER_GRADE_CALLS = 0
FRONTEND_WRONG_RECORD_WRITE = 0                KNOWLEDGE_STATUS_WRITE = 0

AXE_VIOLATIONS = 0                             CONSOLE_ERRORS = 0

TYPECHECK = PASS   LINT = PASS   UNIT_TESTS = PASS (46)   BUILD = PASS
REAL_E2E = PASS (F1C2D 9/9 + supplement 4/4)

BACKEND_CODE_CHANGED = NO                      REAL_APP_DB_MUTATED = NO

FRONTEND_F1C2D_COMPLETE = YES
CHAPTER_PRACTICE_WORKSPACE_FROZEN = YES
BLOCKERS = NONE
```

---

## Non-gating observations

1. **A question-only control renders in the active Summary view.** With the desk on question 1,
   `下一题` is visible while the Summary is showing (`上一题` is not, and at the last question
   `下一题` is not). Clicking it does **not** leave the Summary — it only moves the index used when
   you later open the question review — so per §24 this is `SUMMARY_QUESTION_CONTROL_LEAK = NO`.
   It is still a review-only affordance visible in a view where it has no visible effect; hiding the
   step controls while the Summary is active would remove the ambiguity.
2. **The unanswered confirmation is styled as part of the desk but lands below the fold.** Measured
   geometry: desktop 1440×900 — panel `top=863 / bottom=1076`, both actions at `top=1003`
   (viewport height 900); mobile 390×844 — panel `top=824 / bottom=999`, both actions at `top=938`.
   Its styling is correct (`border-top: 2px solid rgb(12,23,48)` = `--color-lab-ink`, same lab-paper
   panel tint as the summary), so the gate passes, but the message and both actions require a manual
   scroll and nothing moves focus or scrolls to it.
3. `f1c2c-real-vqa.spec.ts` cannot pass while the Vite dev server is pointed at 8952, because that
   spec's own API calls target 8951. Environmental; it belongs to the F1C2C pass and its own port.
