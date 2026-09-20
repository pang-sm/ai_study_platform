# ACCEL_FRONTEND_S3 — Scientific State Workspace

## Scope and implementation

- Frontend-only changes: `frontend/src/features/exam/api/student-twin.ts`, the CS408 Student Twin workspace, its styles, its unit test, and its real-VQA Playwright test.
- The workspace consumes the typed `GET /exam/prep/scientific/capabilities` contract. It requests the Student Twin preview only when the contract includes `component === "student_twin"` with `user_visible === true`.
- The UI never renders a capabilities list. Student Twin is the sole experiment subject; false-visible, shadow, blocked, and other internal components do not enter the user UI.
- The evidence display uses `StudentTwinPreviewResponse.input_summary.event_count`, the backend-declared count of evidence actually used for the current calculation. It does not derive a count from learning records.
- The workspace provides CS408 module selection and a module-preserving link to `/exam/cs408/records`.
- It states the experimental boundary: deterministic engine, real study records, no control over grading, and no changes to knowledge state, wrong answers, or study plans.

## Verification

| Check | Result |
| --- | --- |
| Typecheck | PASS |
| Lint | PASS |
| Unit tests | PASS — 24 files, 84 tests |
| Build | PASS |
| Playwright / real authenticated VQA | PASS — 2 targeted Chromium tests against a temporary migrated database and non-8000 FastAPI service |
| Axe | PASS — zero violations for `.student-twin` in the authenticated preview flow |
| Console checks | PASS — zero page errors or console errors in the authenticated preview and unavailable-state flows |

## Temporary VQA environment

The production-like VQA path used a byte-identical temporary copy of `backend/app.db`. With an explicit temporary `DATABASE_URL`, Alembic upgraded only that copy to `20260919_0010`; `PRAGMA integrity_check` returned `ok`. A fresh FastAPI process ran on `127.0.0.1:8973`, and a temporary isolated runtime process supplied the frozen Student Twin artifact on localhost during the preview check. A disposable authenticated user and factual CS408 practice event existed only in the temporary database.

The preview flow passed with a real Student Twin response, module selection, the module-preserving records link, no internal component leakage, axe, and console checks. A second real browser flow stopped the temporary runtime and verified the bounded unavailable state while learning records remained usable.

## Data and generated artifacts

- Backend source files changed by this task: no.
- Generated API client changed by this task: no.
- Real `backend/app.db` mutated by this task: no; SHA-256 was identical before and after VQA.
- Git cleanup, reset, restore, stash, and commit: none.
- The isolated temporary VQA directory remains under the system temp directory because the execution environment blocked its deletion; it contains the migrated copy and temporary runtime only, never the real database.

## Acceptance status

The frontend implementation and final temporary-environment acceptance are complete. The local real database was never migrated or written.
