# Mobile IA Stage 3 Production Report

## Final status

**MOBILE_IA_STAGE3_FAILED**

Static deployment succeeded, but the mandatory authenticated Production browser acceptance could not be completed. The Production browser opened `/m` and exposed the login form, then repeatedly timed out or reset before credentials could be submitted. A test-account login was authorized for this follow-up attempt, but no credential was transmitted after the browser session failed. Chrome browser control was unavailable in this environment. Authentication was not bypassed, injected, or mocked.

## Commit

- Stage 2 Mobile IA implementation commit: `e0f55da0f65168fdf7ca54bcd653ff7fbe386910`
- Message: `feat(mobile): complete IA stage 2`

Only these implementation files were included in that commit:

- `frontend/src/mobile/MobileApp.jsx`
- `frontend/src/mobile/MobileApp.css`
- `MOBILE_IA_REFACTOR_REPORT.md`
- `MOBILE_IA_STAGE2_REPORT.md`

## Production deployment

- Production URL: `https://101.32.190.42/m`
- Confirmed Nginx static root: `/var/www/ai_study_platform`
- Local entry bundle: `frontend/dist/assets/index-BpA9OTxA.js`
- SHA-256: `BB8554FF35F15DF6E9AA6BFB8A11E525E3E15E259404E7F99A097091E5C4089F`
- Production HTML entry: `/assets/index-BpA9OTxA.js`
- Production bundle HTTP status: `200`
- Public bundle SHA-256: `BB8554FF35F15DF6E9AA6BFB8A11E525E3E15E259404E7F99A097091E5C4089F`
- Backup: `/home/ubuntu/ai-study-platform-backups/mobile-ia-stage3-20260825-112837-dist-before.tgz`

The initial post-upload bundle request returned `404`. Read-only diagnosis showed the deployed `assets/` directory had permission mode `700`, so Nginx could not traverse it. The static artifact permissions were corrected to directory mode `755` and file mode `644`; no Nginx configuration, backend, database, or API was changed. The public bundle then returned `200` with the expected hash.

## Deployment status

`DEPLOYMENT_STATUS: PASS (static artifact delivery)`

## Browser acceptance

Viewport requested: `390 × 844`.

| Check | Result | Evidence |
| --- | --- | --- |
| Production navigation | PASS | `https://101.32.190.42/m` opened with title `AI 学习平台` |
| New bundle loaded by static delivery | PASS | Production HTML and public SHA-256 matched local build |
| DOM / console read | FAIL | Production browser timed out and reset twice |
| Login with existing account | NOT RUN | Login form loaded, then browser reset before the authorized credentials could be entered |
| Profile learning-space switch | NOT RUN | Requires authenticated browser state |
| Knowledge bottom sheet / AI explanation | NOT RUN | Requires authenticated course data |
| PC ↔ Mobile mastery synchronization | NOT RUN | Requires same authenticated PC and Mobile account |
| AI history, upload, edit, regenerate, branch | NOT RUN | Requires authenticated browser state |
| 11408 plan, papers, wrong questions, AI training | NOT RUN | Requires authenticated browser state |

## Screenshots / observed effect

No usable Production screenshot could be captured because the browser control reset while fetching DOM/screenshot state. The observable Production HTTP result is that `/m` serves HTML referencing `index-BpA9OTxA.js`, and the public JavaScript asset returns `200` with the exact local SHA-256 above.

## Test account

- Username: `奶12`
- Password was neither saved nor transmitted after the browser-control failure.

A stable browser connection is required to complete the mandatory login and cross-device verification.
