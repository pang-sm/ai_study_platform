# Mobile IA Stage 4 — Production Acceptance

Date: 2026-08-25  
Production URL: https://101.32.190.42/m  
Final status: **MOBILE_IA_STAGE4_FAILED**

## Delivery identity

| Item | Value |
| --- | --- |
| Application commit | `58b6578a89a75c876b415d88a3aff146ecfd9fb6` |
| Commit message | `refactor(mobile): isolate canonical learning routes` |
| Entry bundle | `assets/index-CI5ANwR0.js` |
| Local SHA-256 | `6B622544369F9A892FD8E19CAAEC0838F1FDC3C1EBF9B4DC719460E96511C53D` |
| Production SHA-256 | `6b622544369f9a892fd8e19caaec0838f1fdc3c1ebf9b4dc719460e96511c53d` |
| Production static root | `/var/www/ai_study_platform` |

The deployed `GET /m` HTML references `assets/index-CI5ANwR0.js`; the public file is present and its server hash matches the local build. The bundle includes `window.MOBILE_BUILD_VERSION`, which reports the build commit and its entry-bundle filename at runtime.

## Completed implementation and static checks

- Canonical mobile routes isolate the learning spaces: `/m/course/*` and `/m/exam11408/*`.
- Legacy `/m/learn`, `/m/tasks`, and `/m/11408` paths normalize to the appropriate canonical space after authentication.
- Course and 11408 bottom navigation targets are distinct; AI chat deep links preserve course/exam context.
- `npm.cmd run build` passed with the commit injected as `VITE_MOBILE_BUILD_COMMIT`.
- `npm.cmd exec eslint src/mobile/MobileApp.jsx src/mobile/buildInfo.js` passed.
- The static deployment changed only frontend assets. No backend, database, API, authentication, PC UI, or Nginx configuration was changed.

## Authenticated browser acceptance

The requested real-account acceptance was **not completed**. The production in-app browser tab was manually authenticated and, before the later connection interruption, visibly rendered the Mobile Shell rather than the PC UI, with these visible controls:

`首页 / 知识点 / AI / 练习 / 我的`

However, the browser-control connection reset twice while obtaining the production page's visible DOM (each attempt timed out at the browser boundary). After the reset, no claimable manually authenticated user tab was available. This prevented safe, evidence-based interaction with the account. No password was entered, stored, transmitted, or recorded by this run.

| Required production scenario | Result | Evidence / reason |
| --- | --- | --- |
| Confirm runtime `MOBILE_BUILD_VERSION` | NOT VERIFIED | DOM/evaluate request timed out before the runtime value could be read. Static bundle evidence is available above. |
| My → Course learning / 11408 centre switch | NOT VERIFIED | Authenticated browser control reset before click validation. |
| Course AI history only | NOT VERIFIED | Authenticated browser control reset before navigation. |
| 11408 AI history only | NOT VERIFIED | Authenticated browser control reset before navigation. |
| Knowledge Bottom Sheet scrolling and fixed actions | NOT VERIFIED | Authenticated browser control reset before navigation. |
| Save mastery through existing API | NOT VERIFIED | Not attempted: it changes user learning data and could not be validated after the reset. |
| PC → Mobile mastery synchronization | NOT VERIFIED | Requires a stable authenticated mobile page and a PC session. |
| Mobile → PC mastery synchronization | NOT VERIFIED | Requires saving mastery in Mobile and a stable PC session. |

## Screenshot evidence

No stable screenshot artifact was produced in this run. The browser interruption occurred before screenshot capture; therefore no screenshot path is reported as verification evidence.

## Modified files for the delivered build

- `frontend/src/mobile/MobileApp.jsx`
- `frontend/src/mobile/buildInfo.js`

This report is a separate acceptance artifact. `frontend/src/main.jsx` was already an uncommitted user worktree change; it was included by the build because it routes `/m` to MobileApp, but it was neither modified nor committed in this stage.

## Required next acceptance action

Re-open a stable manually authenticated production browser session at `https://101.32.190.42/m`, then validate the seven `NOT VERIFIED` scenarios above at 360×800, 390×844, and 412×915. The status remains failed solely because the mandatory real-browser interactions and cross-device synchronization could not be observed after the browser connection reset; it is not a product-functional PASS/FAIL conclusion.
