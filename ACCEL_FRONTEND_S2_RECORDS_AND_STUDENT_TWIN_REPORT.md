# ACCEL_FRONTEND_S2 — Records + Student Twin Acceptance Report

Date: 2026-09-19

## Scope

Implemented two CS408 routes:

- `/exam/cs408/records` — 学习记录档案 / Learning Activity Ledger
- `/exam/cs408/state` — 学习状态实验视图

The CS408 workspace navigation now exposes both routes. No backend, migration, generated
API client, scientific algorithm, SSOT, or real database file was modified.

## Records

- The only timeline query is typed `GET /exam/prep/records`, through `openapi-fetch` and
  TanStack Query's `useInfiniteQuery`.
- Cursor paging is opaque and bounded: the page requests 30 records, retains the server's
  ordering, and asks for the next page only after **加载更多**.
- The module choice is sent as canonical `exam_module_id`; no client-side history merge or
  module filtering occurs.
- The display groups UTC ISO timestamps by browser-local calendar date. A timestamp without an
  explicit offset is not interpreted as a local server timestamp.
- User-facing event mappings are limited to the frozen factual taxonomy. `question_answered`
  renders correct / incorrect / unjudged from the returned `correct` value, and a null score
  never produces a fabricated `0 分`.
- No plan history, wrong-answer lifecycle, audit filtering code, total count, or guessed
  past-paper link is present. `ai_called` is absent because the canonical backend surface does
  not return audit events.

## Student Twin

- The only preview query is typed `GET /exam/prep/scientific/student-twin`, through
  `openapi-fetch` and TanStack Query.
- The UI is read-only. It sends no writes to knowledge, wrong answers, practice, past papers,
  plans, learner state, or Student Twin.
- The required experimental framing is explicit: **学习状态实验视图**, **自研确定性学习状态引擎**,
  real-event source, Scientific Runtime, and no product-decision control.
- The typed state payload is rendered under its original state-engine field names; the UI does
  not relabel values as mastery, ability, confidence, or a prediction.
- Blockers are displayed as bounded technical state. `UNAVAILABLE` renders
  **学习状态服务暂时不可用**, while Records remains usable.
- `misconception_v2` and `tutor_policy` are not queried or shown.

## Automated verification

```text
npm run check
  typecheck: pass
  lint: pass
  vitest: 24 files / 82 tests passed

npm run build
  pass
```

Component tests cover factual answer states, null score, empty Records, module links, cursor
load-more, experiment wording, technical output, blocker rendering, unavailable state, and the
new CS408 navigation entries.

## Real authenticated VQA

The real application ran on fresh, local ports:

```text
FastAPI:            127.0.0.1:8972
Frontend:           127.0.0.1:5173
Scientific Runtime: 127.0.0.1:8971 (available scenario only)
Database:           a fresh TEMP copy, never backend/app.db
Authentication:     real POST /login session against the TEMP database
```

The TEST-only authenticated account was seeded only in the TEMP database because the public
registration flow requires an external email-verification proof. All product interactions and
page reads thereafter used the real HTTP API.

Verified with real data:

- 30+ factual CS408 chapter-practice events plus a real operating-system past-paper event;
  chronology, opaque cursor response, load-more, server-side module filtering, and absence of
  `ai_called`.
- Eligible `question_answered` facts reached the real Student Twin runtime in `PREVIEW` mode;
  `writes_learner_fact=false`, `controls_product_decision=false`, and the old
  `INPUT_FAMILY_NOT_STUDENT_TWIN_ELIGIBLE` blocker was absent.
- Module-scoped preview was fetched from the backend rather than calculated in the browser.
- After stopping the temporary Scientific Runtime, the same real backend produced its bounded
  unavailable response; the state page showed the unavailable copy and Records remained usable.
- AXE violations: 0. Browser console errors: 0.

## Screenshots

Captured under `frontend/.f1c6tmp/screenshots/`:

- `desktop-records.png`
- `desktop-records-filtered.png`
- `desktop-state.png`
- `desktop-state-module.png`
- `desktop-state-unavailable.png`
- `mobile-records.png`
- `mobile-state.png`

## Risk / migration

No database migration is required. The real `backend/app.db` was only copied into a temporary
database before the real VQA run and was not mutated.
