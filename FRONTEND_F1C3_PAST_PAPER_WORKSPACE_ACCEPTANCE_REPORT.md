# FRONTEND_F1C3 — CS408 Past Paper Workspace Acceptance Report

Date: 2026-09-19.
Mode: final real authenticated acceptance. No product source was modified by this pass.

```text
FRONTEND_F1C3_COMPLETE = NO
PAST_PAPER_WORKSPACE_FROZEN = NO
BLOCKER = 1 real frontend defect — figures never render
FRONTEND_CODE_CHANGED = NO     BACKEND_CODE_CHANGED = NO     GENERATED_API_CHANGED = NO
REAL_APP_DB_MUTATED = NO
```

---

# Part A — Deterministic frontend validation

| Check | Result |
| --- | --- |
| `npm run typecheck` | **PASS** |
| `npm run lint` | **PASS** |
| `npm run test:run` | **PASS** — 16 files / **55 tests** |
| `npm run build` | **PASS** |

CS408 shell regression (§36), deterministic specs only:

```
f1c2b-vqa.spec.ts  3 passed   (chapter practice desktop + mobile + scoped Axe)
f1c2c-vqa.spec.ts  3 passed   (feedback, submitted reload, mobile + scoped Axe)
smoke.spec.ts      5 passed   (index, not-found, overflow desktop/mobile, exam entry)
=> 11 passed / 0 failed
```

No regression from F1C3 in any deterministic spec.

---

# Part B — FINAL REAL AUTHENTICATED VQA

| Item | Value |
| --- | --- |
| `BACKEND_VQA_PORT` | **8955** (non-8000; 5173/8000 verified free) |
| `TEMP_DB` | `%TEMP%\f1c3-final\vqa.db` (disposable copy of the real DB, reseeded user) |
| Backend | real `main:app` on uvicorn, real routes, real grading, real persistence |
| Frontend | real Vite dev server, `VITE_API_BASE_URL=http://127.0.0.1:8955` |
| Auth | real `POST /login` → real `ai_session` cookie in the browser context |
| Spec | `frontend/tests/e2e/f1c3-real-vqa.spec.ts` — no `page.route` anywhere |

```text
REAL_AUTH_SESSION = PASS
```

## Both normalized sources exercised

| | data_structure 2022 | operating_system 2022 |
| --- | --- | --- |
| normalized source | **document** | **bank** |
| questions | 13 (11 choice + 2 big) | 12 (10 choice + 2 big) |
| figures | every question carries one | q45 ×2, **q46 ×1 (the BC6-recovered figure)** |
| dossier → paper → attempt → save → submit → replay | PASS | PASS |
| frontend behaviour | identical | identical |

```text
DOCUMENT_SOURCE_REAL = PASS
BANK_SOURCE_REAL     = PASS (full lifecycle; only the figure render fails, see the blocker)
```

The UI never learns which source answered. Asserted at runtime by lower-casing the whole rendered
page and rejecting `bank / document / ocr / cache / source / 来源 / 题库来源`, and by the component
never reading the `source` field the API returns.

```text
SOURCE_BRANCHING_IN_UI = 0        SOURCE_SPECIFIC_COMPONENT_BRANCHES = 0
```

## Identity

Route context is `?module=<subject_key>&year=<year>&attempt=<id>` — the public paper identity, never
an internal id. Questions are identified and displayed by `question_number` (`第 46 题`), the
navigator is labelled with the official numbers (23…32, 45, 46) and the result map is keyed by
`question_number`.

```text
PUBLIC_PAPER_IDENTITY    = PASS      PUBLIC_QUESTION_IDENTITY = PASS
QUESTION_INDEX_AS_IDENTITY = NO
```

## Year index

The rendered years and counts equal the normalized backend payload exactly (`papers[]` from
`GET …/past-papers`), each row verified as `year` + `question_count 道真题`. Nothing is hardcoded.

```text
REAL_YEAR_INDEX = PASS        HARDCODED_FAKE_YEARS = 0
```

## Pre-submit security

Every API response the browser received before submit was walked recursively for
`standard_answer / analysis / correct / judge / score`:

```
question list (document + bank)   -> no protected key
in-progress attempt detail        -> no protected key, and no `results` key
```

```text
PRE_SUBMIT_ANSWER_LEAK         = 0
PRE_SUBMIT_EXPLANATION_LEAK    = 0
PRE_SUBMIT_GRADING_RESULT_LEAK = 0
```

## Attempt / objective / subjective

The attempt defines the question set: `detail.questions[].question_number` equals the paper's list
exactly, and no phantom question renders.

```text
ATTEMPT_DEFINES_QUESTION_SET = PASS      PHANTOM_QUESTION_RENDERING = 0
OBJECTIVE_FLOW_REAL = PASS               FRONTEND_GRADING_COMPARISON = 0
SUBJECTIVE_SELF_REVIEW_REAL = PASS       FAKE_MIDPOINT_SCORE_RENDERED = 0
```

Objective result renders 回答正确/回答错误 + 你的答案 + 正确答案 straight from the server verdict.
Subjective renders 自行复盘 + 你的作答 + 参考答案 with the real reference answer, and **none** of
回答正确 / 回答错误 / 得分 / 自动评分 / AI判分 / `5/10` / any `%`.

Static analysis is absent for these rows and no empty 题目解析 block appears:

```text
STATIC_ANALYSIS_OPTIONAL = PASS
```

## Replay, rehydration and view mode

```
submit -> summary -> refresh -> submitted detail replay -> identical counts
查看答题纸 -> 本次答卷 -> both directions, with status='submitted' not forcing either surface
refresh -> submitted option restored and disabled; submitted text restored and disabled
```

```text
OBJECTIVE_RESULT_RELOAD_REAL     = PASS
SELF_REVIEW_RELOAD_REAL          = PASS
SUBMITTED_INPUT_REHYDRATION_REAL = PASS
SUBMITTED_VIEW_MODE_REAL         = PASS
```

## Summary and boundaries

The summary is derived only from the server's submitted results, with expected counts computed
independently in the spec from the raw API payload:

```
已作答 N · 未作答 M
客观题答对 A · 客观题答错 B · 自行复盘 C
```

Unanswered stays separate from incorrect. No accuracy percentage is rendered at all, so its
denominator cannot include ungraded rows.

```text
PAPER_SUMMARY_REAL = PASS        UNANSWERED_EQUALS_INCORRECT = NO
ACCURACY_GRADED_ONLY = PASS (no accuracy surface exists; nothing ungraded can enter one)
FRONTEND_WRONG_RECORD_WRITE = 0  KNOWLEDGE_STATUS_WRITE = 0
```

Boundary proof: every request the browser made was recorded and none targeted a grading, wrong-book
or mastery path — only the past-paper index / questions / attempts / answers / submit endpoints.

## Image delivery over HTTP

Backend + transport are correct. Representative repaired and cross-source cases, each fetched over
real HTTP with the real session:

| Case | URL | Result |
| --- | --- | --- |
| extension fallback (`.jpg` mapped, `.jpeg` on disk) | `operating_system/2022/2022_23_0.jpg` | 200 image/jpeg |
| derived deterministic layout | `computer_organization/2022/q12_0.jpg` | 200 image/jpeg |
| cross-source resolution (Q46) | `operating_system/2022/img_14.jpg` | 200 image/jpeg |
| document source | `data_structure/2022/img_0.jpg` | 200 image/jpeg |

Every advertised resource across both papers was fetched: all 200, and every URL matched
`^/exam/11408/past-paper-images/[a-z_]+/\d{4}/[A-Za-z0-9._-]+$` — no filesystem path, no Windows
path, no traversal.

```text
RESOURCE_PATH_LEAK = 0
NORMALIZED_IMAGE_RESOURCE_REAL = PARTIAL — backend/HTTP PASS, frontend rendering FAIL (blocker)
```

## Accessibility and console

axe, scoped to `.past-paper`, on the real pages: dossier index, year list, question desk, objective
result, submitted review, mobile index, mobile question, mobile summary.

```text
AXE_VIOLATIONS = 0        CONSOLE_ERRORS = 0
```

Headings are semantic, radios are real `<fieldset>`/`<label>` controls with a shared name, the
figure carries an `alt` that names the question, the navigator sets `aria-current="step"`, results
pair a colour rule with explicit text, and mobile has no horizontal overflow
(`scrollWidth − clientWidth = 0`).

## Screenshots

`%TEMP%\f1c3-final\screenshots\` — all ten required captures, all inspected.

| File | Viewport | Note |
| --- | --- | --- |
| `real-desktop-past-paper-index.png` | 1440×900 | module dossier |
| `real-desktop-past-paper-year-list.png` | 1440×900 | real years + counts |
| `real-desktop-past-paper-question.png` | 1440×900 | document-source question |
| `real-desktop-past-paper-figure-question.png` | 1440×900 | **figure absent — the blocker** |
| `real-desktop-past-paper-objective-result.png` | 1440×900 | 回答正确/错误 + answers |
| `real-desktop-past-paper-self-review.png` | 1440×900 | 自行复盘 + answers |
| `real-desktop-past-paper-summary.png` | 1440×900 | factual counts |
| `real-mobile-past-paper-index.png` | 390×844 | module dossier |
| `real-mobile-past-paper-question.png` | 390×844 | question desk |
| `real-mobile-past-paper-summary.png` | 390×844 | summary |

**PAST_PAPER_DOSSIER_REAL = PASS.** The index reads as 历年真题档案: an eyebrow (`CS408 / 历年试卷档案`),
the module as the page title, then `真实年份试卷` with one row per real year — tabular year, the
official paper name, the real question count and a rule-separated row. No card grid, no admin table,
no dashboard, no KPI tiles.

**TECHNICAL_EXAM_DESK_REAL = PASS.** The question view carries the same desk language as the rest of
CS408: `lab-ink` rules, lab-paper panel tint, the module name large in the header, the official
number as `第 N 题 · 简答题 · 2022 年真题`, the stem as the visual centre, the numbered navigator on the
left. Not a quiz app, not a dashboard, not a marketing hero.

## Database safety

| Measure | Value |
| --- | --- |
| SHA256 | `1c1b2d85…3fe522` — identical to baseline |
| size / mtime | `64917504` / `2026-09-16 21:24:23` — identical |
| `integrity_check` / `quick_check` | `ok` / `ok` |
| table count | 72 |
| protected counts | `exam_question_bank` 9333, `programming_exercises` 1923, `knowledge_points` 32 |
| `past_paper_attempts` / `past_paper_wrong_questions` | 0 / 0 |
| `app.db-wal` | 0 bytes |

All VQA writes went to `%TEMP%\f1c3-final\vqa.db`; the real file was only ever opened `?mode=ro`.

```text
REAL_APP_DB_MUTATED = NO
```

---

# BLOCKER — figures never render

**Affected component**: `frontend/src/features/exam/components/cs408-past-paper-workspace.tsx:22`

```tsx
{question.resources.map((resource, index) => (
  <img key={resource.url} className="past-paper-question__figure"
       src={resource.url}                      // <-- resolves against the PAGE origin
       alt={`第 ${question.question_number} 题图示 ${index + 1}`}
       onError={(event) => { event.currentTarget.hidden = true; }} />
))}
```

**Expected**: the figure loads from the API and appears near the stem.

**Actual**: `resource.url` is API-base-relative by contract, but the component uses it verbatim, so
the browser resolves it against the page origin (the Vite dev server) instead of `env.apiBaseUrl`.
The request never reaches the backend; `onError` fires and hides the image.

Captured at runtime from the browser:

```
page origin   : http://127.0.0.1:5173
img attr src  : /exam/11408/past-paper-images/operating_system/2022/img_14.jpg
img resolved  : http://127.0.0.1:5173/exam/…/img_14.jpg      <-- frontend host, not the API
network requests to past-paper-images : NONE
img hidden    : true   naturalWidth : 0
same URL via the API base + session   : 200 image/jpeg
```

`curl http://127.0.0.1:5173/exam/…/img_14.jpg` returns `200 text/html` — the SPA fallback, not an
image. This is not environment-specific: in production the page origin is the site root and the same
bare path hits the SPA fallback identically. The component has no proxy and no asset-URL helper;
`env.apiBaseUrl` is currently used only by `src/lib/api/client.ts`.

**Reproduction**: open any past-paper question that has a figure (e.g.
`/exam/cs408/past-papers?module=operating_system&year=2022`, question 46). The stem reads
「题46 图表示…」 and no diagram appears. Visible in `real-desktop-past-paper-figure-question.png`.

**Failing tests**: `f1c3-real-vqa.spec.ts` › `BANK source: … recovered Q46 figure` and › `mobile: …`
— both fail on `expect(figure).toBeVisible()` after every other assertion in the test has passed.

**Indicative fix** (not applied — this pass is acceptance-only):
`src={`${env.apiBaseUrl}${resource.url}`}`, which yields `http://127.0.0.1:8955/exam/…` locally and
`/api/exam/…` behind nginx, matching the one URL format BC6 established.

```text
REAL_FIGURE_RENDERING = FAIL
```

---

# Final gates

```text
REAL_AUTH_SESSION = PASS

DOCUMENT_SOURCE_REAL = PASS
BANK_SOURCE_REAL     = PASS (lifecycle) / figure render FAIL

SOURCE_BRANCHING_IN_UI = 0            SOURCE_SPECIFIC_COMPONENT_BRANCHES = 0

PUBLIC_PAPER_IDENTITY    = PASS
PUBLIC_QUESTION_IDENTITY = PASS
QUESTION_INDEX_AS_IDENTITY = NO

REAL_YEAR_INDEX = PASS                HARDCODED_FAKE_YEARS = 0

ATTEMPT_DEFINES_QUESTION_SET = PASS   PHANTOM_QUESTION_RENDERING = 0

PRE_SUBMIT_ANSWER_LEAK         = 0
PRE_SUBMIT_EXPLANATION_LEAK    = 0
PRE_SUBMIT_GRADING_RESULT_LEAK = 0

OBJECTIVE_FLOW_REAL = PASS            FRONTEND_GRADING_COMPARISON = 0
SUBJECTIVE_SELF_REVIEW_REAL = PASS    FAKE_MIDPOINT_SCORE_RENDERED = 0
STATIC_ANALYSIS_OPTIONAL = PASS

NORMALIZED_IMAGE_RESOURCE_REAL = PARTIAL (backend + HTTP PASS, UI render FAIL)
RESOURCE_PATH_LEAK   = 0
REAL_FIGURE_RENDERING = FAIL          <-- blocker

OBJECTIVE_RESULT_RELOAD_REAL     = PASS
SELF_REVIEW_RELOAD_REAL          = PASS
SUBMITTED_INPUT_REHYDRATION_REAL = PASS
SUBMITTED_VIEW_MODE_REAL         = PASS

PAPER_SUMMARY_REAL = PASS             UNANSWERED_EQUALS_INCORRECT = NO
ACCURACY_GRADED_ONLY = PASS

FRONTEND_WRONG_RECORD_WRITE = 0       KNOWLEDGE_STATUS_WRITE = 0

PAST_PAPER_DOSSIER_REAL  = PASS
TECHNICAL_EXAM_DESK_REAL = PASS

AXE_VIOLATIONS = 0                    CONSOLE_ERRORS = 0

TYPECHECK = PASS   LINT = PASS   UNIT_TESTS = PASS (55)   BUILD = PASS
REAL_AUTH_VQA = PARTIAL — every scenario passes except figure rendering

BACKEND_CODE_CHANGED   = NO
GENERATED_API_CHANGED  = NO
REAL_APP_DB_MUTATED    = NO

FRONTEND_F1C3_COMPLETE = NO
PAST_PAPER_WORKSPACE_FROZEN = NO
```

---

## HARNESS_DEBT (not product defects)

Pre-existing real-backend specs hardcode their own backend port and therefore fail when this pass
runs its own environment. None of them exercises F1C3, and none was changed:

| Spec | Needs | Status in this pass |
| --- | --- | --- |
| `f1c2c-real-vqa.spec.ts` | a backend on **8951** | 1 test hit, failed on connect |
| `f1c2d-real-vqa.spec.ts` | a backend on **8952** | 8 tests, failed on connect |
| `f1c2d-supplement-real.spec.ts` | a backend on **8952** | 4 tests, failed on connect |
| `f1c2d-r2-real-smoke.spec.ts` | its own real backend | 1 test, failed on connect |

Full-suite tally: `14 passed / 17 failed / 8 skipped`, where **15 of the 17 failures are this
harness debt** and **2 are the F1C3 figure blocker**.

## Carried forward

* `ACCEPTANCE_RESOLUTION` (not a product issue): with no accuracy surface rendered, `ACCURACY_GRADED_ONLY`
  is satisfied trivially — if an accuracy readout is ever added, its denominator must stay
  `correct + incorrect` over the server's authoritative verdicts.
* The task's §34 screenshot list is fully captured even though two specs fail, because the
  assertions were ordered so every capture happens before the failing figure check.

---

# F1C3-R1 RESOURCE URL CLOSURE

## Root cause and repair

`PastPaperResource.url` is a public **API-base-relative** path. The answer desk previously used the
path directly in `<img src>`, so a browser on the Vite origin requested `5173/exam/...`; Vite's SPA
fallback replied with HTML and the image `onError` hid the figure.

The frontend now has one shared `resolveApiResourceUrl()` helper in `frontend/src/lib/api/client.ts`.
It composes a normalized resource path with `env.apiBaseUrl`, including a configured API base
pathname, and is the only resource URL composition used by the Past Paper component. No filename,
source or filesystem-path logic was added.

## R1 real-browser evidence

The targeted real VQA ran against FastAPI on `127.0.0.1:8955` using a disposable TEMP database and
Vite configured with `VITE_API_BASE_URL=http://127.0.0.1:8955`.

| Gate | Result |
| --- | --- |
| Operating System 2022 Q46 image | PASS — visible and decoded |
| Browser `currentSrc` | `http://127.0.0.1:8955/exam/11408/past-paper-images/...` |
| Image completion | `complete === true`, `naturalWidth > 0`, `naturalHeight > 0` |
| HTTP / MIME | `200`, `image/jpeg` |
| jpg/jpeg fallback | PASS |
| derived `q{n}_{i}` resource | PASS |
| cross-source Q46 resource | PASS |
| document-backed resource | PASS |
| scoped Axe / console | `0` violations / `0` errors |

`tests/e2e/f1c3-real-vqa.spec.ts` completed 5/5 scenarios. The Q46 screenshot is at
`%TEMP%\\f1c3-final\\screenshots\\real-desktop-past-paper-figure-question.png` and now includes the
diagram.

```text
RESOURCE_URL_RESOLVED_AGAINST_API_BASE = PASS
RESOURCE_REQUEST_USES_FRONTEND_ORIGIN = NO
RESOURCE_SOURCE_BRANCHING = 0
OPERATING_SYSTEM_2022_Q46_IMAGE = PASS
RESOURCE_HTTP_STATUS = 200
RESOURCE_CONTENT_TYPE = image/jpeg
IMAGE_COMPLETE = true
IMAGE_NATURAL_WIDTH_GT_0 = PASS
IMAGE_NATURAL_HEIGHT_GT_0 = PASS
IMAGE_ONERROR_FIRED = NO
JPG_JPEG_CASE = PASS
DERIVED_QNI_CASE = PASS
CROSS_SOURCE_Q46_CASE = PASS
TARGETED_PLAYWRIGHT = PASS
REAL_AUTH_SMOKE = PASS
BACKEND_FILES_CHANGED = 0
GENERATED_API_CHANGED = NO
FRONTEND_F1C3_R1_COMPLETE = YES
FRONTEND_F1C3_COMPLETE = YES
PAST_PAPER_WORKSPACE_FROZEN = YES
```
