# Legacy programming cleanup audit

- Baseline commit: `7fe140f`
- Cleanup commit: `be37cce`
- Baseline production status: `PRODUCTION_UI_VERIFIED`
- Final cleanup status: `LEGACY_PROGRAMMING_CLEANUP_VERIFIED`
- Production URL: `http://101.32.190.42/`
- Database changed: no
- Database records deleted: no
- Security follow-up: `HTTPS_REQUIRED_BEFORE_PRODUCTION_SECURITY_FREEZE`

## Chain mapping

| Entry | Current component | Current API/data | Final status |
|---|---|---|---|
| `programmingHome` | `ProgrammingHome` -> `ProgrammingWorkbench` | `/programming/exercises*`, `/code/projects*`, `/code/analyze`, `/code/interactive-run`; `ProgrammingExercise`, `CodeProject`, progress/submission models | User-facing and verified |
| `codeStudio` | `CodeStudio` and private subcomponents | `/code/sessions*`, `/code/challenges*`, `/code/execute`, `/code/attempts`, `/code/progress`, legacy AI endpoints; legacy models | Hidden compatibility only; not mounted from current App entry points |

## Cleanup performed

- Replaced visible `codeStudio` navigation, home, search, practice, activity, and search-result targets with `programmingHome`.
- Normalized stale `ai_study_current_page=codeStudio` to the new programming home.
- Removed the active `CodeStudio` lazy render path from `App.jsx`.
- Kept legacy APIs, models, components, and historical records because deletion was not justified by this audit.
- Kept `/code/projects*`, `/code/analyze`, and `/code/interactive-run`; these are still used by the verified Workbench.
- No database migration, deletion, or data rewrite was performed.

## Stale-state production probe

The probe created a fresh authenticated context and injected `ai_study_current_page=codeStudio` before opening the production site.

- Result: `stale_state_migrated`
- `ProgrammingHome` count: `1`
- `CodeStudio` shell count: `0`
- Legacy sidebar count: `0`
- Console errors: `0`
- Failed business API responses: `0`
- Evidence: `verification-results/p2-legacy-audit/old-entry-click.json`
- Screenshot: `verification-results/p2-legacy-audit/old-entry-click.png`

This verifies the old stored page state does not reopen the legacy page or leave the user in a legacy shell.

## Production regression

The deployed new chain was exercised with independent authenticated contexts for:

- Python exercise `1629`
- C++ exercise `1734`
- Java multi-file exercise `1546`

Each target passed question lookup, Workbench identity, starter/Monaco loading, run, single and all public tests, submission, topic switching without residue, and (for Java) multi-file list/scroll verification. Hidden/reference content was not exposed. The run recorded zero console errors and zero failed business API responses.

Evidence:

- Full regression: `verification-results/p2-legacy-audit/full-regression/programming-workbench-cli-acceptance.json`
- Screenshots: `verification-results/p2-legacy-audit/screenshots/`
- Stale-state probe: `verification-results/p2-legacy-audit/old-entry-click.json`
- Stale-state screenshot: `verification-results/p2-legacy-audit/old-entry-click.png`

## Validation and deployment

- Frontend build: passed
- Python compile: passed
- Backend tests: `14 passed`
- Production health: `GET http://101.32.190.42/api/health` -> `200`, `{"status":"ok"}`
- Actions: [31241549720](https://github.com/pang-sm/ai_study_platform/actions/runs/31241549720) -> success

## Final classification

- Remove/replace user-visible legacy entry references: completed.
- Retain hidden compatibility for historical data: completed.
- Retain verified Workbench dependencies: completed.
- Legacy backend/API/model deletion: intentionally not performed.

No further P2 cleanup is required for the scoped legacy programming entry problem. Future removal of compatibility code requires a separate historical-data dependency audit.
