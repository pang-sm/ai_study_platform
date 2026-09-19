# FRONTEND_F1B1 — Exam Profile and Catalog Acceptance Report

## 1. Git safety

No reset, clean, restore, stash, commit, merge, rebase, pull, or push was used. The pre-existing dirty worktree was preserved.

## 2. Visual baseline

The F1A shell, deep-ink header, warm paper canvas, context navigation, ruled dividers, and 1280px content measure were retained.

## 3. API integration

`GET /exam/prep/profile`, `PUT /exam/prep/profile`, `GET /exam/prep/catalog`, and `GET /exam/prep/subjects/{subject_id}/content-status` are accessed only through typed `openapi-fetch` hooks. Missing successful payloads are rejected as controlled API errors.

## 4. My Exam

`/exam` renders an intentional unconfigured entry state and a configured exam dossier with real target year, catalog-resolved selected track, selected active subjects, framework-only subjects, unknown/stale subject safety, and the deterministic CS408 entry action.

## 5. Setup

`/exam/setup` has native radio/checkbox controls and an optional numeric target year. Changing direction does not modify selected subjects. A successful PUT updates only the profile cache and returns to `/exam`.

## 6. Subject catalog

`/exam/subjects` groups ruled rows by the categories supplied by the catalog, with no fabricated course metrics or card grid.

## 7. Framework-only UX

The frozen terminology is used: `内容建设中`. The detail state is explicit that content can be selected for preparation but is not presently studyable, without fake content below it.

## 8. Unknown profile subject

The generated normal/unknown union is narrowed before display. An unknown stored ID is kept, labelled conservatively, and offers a safe route to edit setup; it is never silently removed.

## 9. Query/cache semantics

Stable keys are scoped to exam profile, catalog, and subject content status. Profile mutation updates only the profile cache. Catalog uses a five-minute stale window.

## 10. Auth state

A 401 renders the bounded `需要登录` state. No unsupported login route was added. `FUTURE_AUTH_SURFACE` remains outstanding.

## 11. Responsive

The retained shell has existing desktop/mobile no-horizontal-overflow Playwright coverage. Dedicated visual review with a live seeded profile was not run in this workspace.

## 12. Accessibility

Native fieldsets, legends, radios, checkboxes, labels, 44px rows, visible focus styling, route `aria-current`, and non-colour availability text are retained. Existing Playwright axe checks pass for the homepage and CS408 foundation.

## 13. Visual QA

No visual claims are made for real profile/catalog data: a safe current backend fixture was not started. The implementation follows the F1A editorial/ruled-list language and avoids images, dashboards, bento grids, progress indicators, and fabricated study data.

## 14. Homepage regression

Homepage smoke, desktop overflow, mobile overflow, console, and axe checks passed. No homepage files were changed by F1B1.

## 15. Tests

- Unit: 7 files, 19 tests passed (`npm run test:run`).
- Added profile view-model, product rendering, framework relationship, and missing-success-payload coverage.
- E2E: 5 Chromium tests passed (`npm run test:e2e`). The F1A dynamic subject-detail assertion was removed because this screen now correctly needs a protected real API response rather than static placeholder content.

## 16. Contract gaps

No generated transport gap remains for F1B1. A runnable authenticated, seeded backend fixture remains required to perform the requested full real-data visual flows and end-to-end save journey.

## 17. Changed files

- `frontend/src/features/exam/api/{profile,catalog,content-status}.ts`
- `frontend/src/features/exam/components/{exam-product-pages,content-unavailable-state}.tsx`
- `frontend/src/features/exam/view-models/profile.ts`
- `frontend/src/features/exam/components/*test.tsx`
- `frontend/tests/e2e/smoke.spec.ts`
- The four F1B1 route files under `frontend/src/routes/exam/`

No `backend/**` or migration file was changed by this task.

## 18. Final gates

| Gate | Status |
| --- | --- |
| GENERATED_TRANSPORT_TYPES_ONLY | PASS |
| HAND_WRITTEN_TRANSPORT_DTOS | 0 |
| MY_EXAM_PAGE / EXAM_SETUP_PAGE / SUBJECT_CATALOG_PAGE / SUBJECT_DETAIL_PAGE | PASS (unit/build verified) |
| PROFILE states / framework-only / unknown profile subject | PASS (unit verified) |
| CS408 active entry | PASS |
| FAKE_PROGRESS_METRICS / FAKE_CONTENT | 0 |
| BACKEND_FILES_CHANGED | 0 |
| HOMEPAGE_VISUAL_REGRESSION | NO (smoke coverage) |
| AXE_VIOLATIONS / CONSOLE_ERRORS | 0 in the passing Playwright scenarios |
| TYPECHECK / LINT / UNIT_TESTS / BUILD / E2E | PASS |
| Desktop/tablet/mobile real-data visual QA | NOT RUN |

## Authenticated Real-Data Visual QA

- QA backend: current backend runtime at `127.0.0.1:8017`; port 8000 was not used.
- Database: `TEMP/zhixue-f1b1-vqa/exam-vqa.sqlite3` only; `backend/app.db` was not opened or changed.
- Auth: a temporary real `users`/`auth_sessions` session was seeded for the configured profile (`cs_408`, `cs_408 + math_1`, target year 2027) and a separate no-profile user.
- Contract: browser requests were Playwright-routed only to the isolated current backend, with real backend responses used unchanged.
- Screenshots: `%TEMP%/zhixue-f1b1-vqa/screenshots/` includes configured desktop, setup, catalog, framework-only detail, configured mobile, setup mobile, configured tablet, and unconfigured tablet captures.

Visual ledger:

| Surface | Observed issue | Fix made | Final status |
| --- | --- | --- | --- |
| Configured `/exam` | Active availability badge contrast was 3.14:1 | Deepened active badge text to `text-emerald-800` | Pass |
| `/exam/setup` | Category headings skipped from page h1 to h3 | Promoted catalog category headings to h2 | Pass |
| Framework-only detail | FastAPI's nested `detail` shape was rendered as a generic failure | Normalizer now unwraps structured `detail` | Pass |
| Desktop/tablet/mobile surfaces | No clipping, overflow, fake content, or layout regression observed | None | Pass |

All real-data VQA cases passed with axe zero violations. The browser emits a resource-level 409 log for the intentional framework-only content gate; it is an expected backend contract response, rendered as the dedicated availability state, and is excluded from actionable console-error accounting. No script/runtime console errors occurred.

`FRONTEND_F1B1_COMPLETE = YES`, `FRONTEND_F1B1 = FROZEN`, and `FRONTEND_F1B2_READY = YES` after the final gates below.
