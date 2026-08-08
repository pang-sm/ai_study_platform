# Profile actions production acceptance summary

- Target: `http://101.32.190.42/`
- Business patch: `836ae2b` (`fix: remove fake profile actions`)
- Production deploy for that patch: successful Actions run `31243485053`
- Raw browser evidence: `profile-actions-acceptance.json`

## Last real browser run

| Check | Result |
|---|---|
| Profile load | PASS |
| Fake phone / bulk-clear / account-delete controls absent | PASS |
| Profile save API | PASS (`PUT /api/me/profile` = 200) |
| Profile persistence API after reload | PASS (`/api/me` = 200, updated profile returned) |
| Membership/quota | PASS (entitlements = 200) |
| Programming -> course | PASS |
| Course -> 11408 | PASS |
| 11408 -> programming | PASS |
| Logout | PASS (`/api/logout` = 200) |
| Private API after logout | PASS (`/api/me` = 401) |
| Reload after logout | PASS (login form visible) |

The 401 responses after logout are expected evidence of session revocation. The first version of the acceptance script incorrectly counted them as failures; the script now excludes only these expected post-logout responses.

## Script correction pending rerun

`scripts/acceptance/profile_actions_acceptance.mjs` now waits for the initial `/api/me` response after reload before checking the Profile UI, uses the refreshed API user for persistence, and records direction destination completion without depending on a response-listener race.

The complete run intentionally ended with logout, so the saved test session is revoked. A fresh manual login is required before rerunning the corrected script. The raw report is preserved and is not overwritten.

## Evidence

- [profile-actions-acceptance.json](C:/Users/26477/Desktop/ai_study_platform/verification-results/profile-actions-production/profile-actions-acceptance.json)
- [profile-programming.png](C:/Users/26477/Desktop/ai_study_platform/verification-results/profile-actions-production/screenshots/profile-programming.png)
- [direction-switch-programming.png](C:/Users/26477/Desktop/ai_study_platform/verification-results/profile-actions-production/screenshots/direction-switch-programming.png)
- [logout-result.png](C:/Users/26477/Desktop/ai_study_platform/verification-results/profile-actions-production/screenshots/logout-result.png)

## Status

`PROFILE_ACTIONS_CLEANUP_NOT_VERIFIED`

Reason: the corrected script has not yet been rerun with a newly authenticated session after the prior run revoked the test session.
