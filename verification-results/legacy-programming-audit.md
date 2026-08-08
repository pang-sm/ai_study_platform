# Legacy programming audit

- Baseline commit: `7fe140f`
- Baseline production status: `PRODUCTION_UI_VERIFIED`
- Production URL: `http://101.32.190.42/`
- Database changed: no
- Database records deleted: no

## Chain mapping

| Entry | Current component | Current API/data | User-facing status |
|---|---|---|---|
| `programmingHome` | `ProgrammingHome` → `ProgrammingWorkbench` | `/programming/exercises*`, `/code/projects*`, `/code/analyze`, `/code/interactive-run`; `ProgrammingExercise`, `CodeProject`, progress/submission models | Verified new chain |
| `codeStudio` | `CodeStudio` | `/code/sessions*`, `/code/challenges*`, `/code/execute`, `/code/attempts`, `/code/progress`, legacy AI endpoints; `CodeSession`, `CodeChallenge`, attempt/message models | Legacy frontend references remain |

## Findings

1. `frontend/src/config/navigation.js` exposes `codeStudio` as “编程学习助手” in the sidebar and home search configuration.
2. `frontend/src/components/HomePage.jsx` exposes a `codeStudio` shortcut.
3. `frontend/src/components/GlobalSearchBox.jsx` exposes a `codeStudio` search result.
4. `frontend/src/components/PracticeCenter.jsx` sends programming questions to `codeStudio`.
5. `frontend/src/App.jsx` still lazy-loads and renders `CodeStudio`, accepts `codeStudio` as a valid saved page, and has the old feature gate.
6. `/code/projects*`, `/code/analyze`, and `/code/interactive-run` are not legacy-only: the verified `ProgrammingWorkbench` calls them. They must remain.
7. The current authenticated production session opened the new `CourseLearningHome`; the old sidebar was not present, so the old-entry probe did not reach `CodeStudio`. This is recorded as a routing/state observation, not as a successful cleanup.

## Classification

- A — remove or replace direct user-facing `codeStudio` entry references.
- B — retain legacy component, models, and APIs hidden behind compatibility while historical data dependence is audited.
- C — retain the new Workbench component, project/file models, exercise APIs, execution WebSocket, and AI Coach `/code/analyze` path.

## Production evidence

- New-chain smoke: `verification-results/p2-legacy-audit/programming-workbench-cli-acceptance.json`
- Old-entry probe: `verification-results/p2-legacy-audit/old-entry-click.json`
- Old-entry screenshot: `verification-results/p2-legacy-audit/old-entry-click.png`

The next patch is intentionally limited to redirecting stale frontend entry/state to `programmingHome`; no backend API or database deletion is justified by this audit alone.

## Local cleanup patch result

- All visible `codeStudio` navigation, home, search, practice, search-result, activity, and practice-list targets now resolve to `programmingHome`.
- Stale `ai_study_current_page=codeStudio` is normalized to `programmingHome`.
- The `CodeStudio` lazy render path is no longer mounted by `App.jsx`.
- Legacy components, APIs, models, and historical records were not deleted.
- Database changed: no.
- `frontend/npm run build`: passed.
- Python compile: passed.
- Backend tests: 14 passed.

The patch is local and still requires commit, deployment, and production regression of Python 1629, C++ 1734, Java 1546, refresh, back navigation, and stale-page migration.
