# Profile actions audit

- Baseline: `PRODUCTION_UI_VERIFIED`
- Scope: generic and direction-specific profile pages, profile settings, logout, membership/quota, and direction switching.
- Audit status: `AUDIT_COMPLETE_BEFORE_PATCH`
- Database changes during audit: none

## Current routing

The legacy `page=profile` entry is redirected by `App.jsx` to the active direction profile:

| Entry | Current page |
|---|---|
| `profile` | active direction profile |
| `courseProfile` | `CourseLearningProfile` |
| `examProfile` | `ExamProfile` |
| `programmingProfile` | `ProgrammingProfile` |

## Button -> handler -> API -> data impact

| Action | Current handler | Current API | Data impact | Classification |
|---|---|---|---|---|
| Basic profile | `handleSave` / `saveBasicInfo` | `PUT /api/me/profile` | User profile and learning settings | A: real |
| Avatar | `handleAvatarUpload` / `uploadAvatar` | `POST /api/me/avatar` | User avatar and uploaded file | A: real |
| Password | `handleChangePassword` / `changePassword` | `PUT /api/me/password` | Password hash | A: real; needs regression |
| Email | `sendEmailCode` / verify handler | `/me/email/send-code`, `/me/email/verify` | Email and verification flag | A: real, SMTP-dependent |
| Logout | `App.logout` | `POST /api/logout` | Revokes `AuthSession`, clears cookie | A: real |
| Membership/quota | profile fetchers | `/me`, `/me/quota`, programming entitlements | Read-only membership and quota | A: real |
| Direction switch | `switchLearningDirection` | `POST /api/me` then entitlement check | Track selection/navigation | A: real; needs regression |
| Phone | toast / error only | none | none | B: fake entry |
| Clear chat | confirm then `showToast` | none | none | B: fake entry |
| Clear learning | confirm then `showToast` | none | none | B: fake entry |
| Clear practice | confirm then `showToast` | none | none | B: fake entry |
| Delete account | confirm then `showToast` | none for self-service | none | B: fake entry |

## Findings

1. Phone modification is shown in all direction profiles, but no SMS provider, verification flow, anti-abuse control, or self-service phone API exists.
2. The generic `ProfilePage` exposes three bulk-clear controls that only show `功能开发中` after confirmation.
3. The generic `ProfilePage` exposes account deletion that only shows a not-supported toast. The `User` model has inactive/deleted fields, but no safe self-service deletion endpoint is wired.
4. Basic profile, avatar, password, email verification, logout, quota/membership and direction switching have real frontend/backend paths and should be preserved and regression-tested.
5. Email binding is a real flow but returns service-unavailable when SMTP is not configured; this is an operational limitation, not a fake success path.
6. No database deletion or new destructive endpoint is justified for this patch.

## Planned minimal patch

- Remove the phone modification buttons and present the phone value as read-only.
- Remove the three generic bulk-clear controls.
- Remove the generic self-service account deletion control.
- Leave existing backend compatibility APIs and historical data untouched.
- Regress real profile save, logout, password, direction, membership/quota and main entry points in production.

## Patch and production evidence

- Patch commit: `836ae2b`
- Deployment Actions run: `31243485053` (successful)
- `/api/health`: `200`, `{"status":"ok"}`
- Raw browser report: `verification-results/profile-actions-production/profile-actions-acceptance.json`
- Final summary: `verification-results/profile-actions-production/profile-actions-final-summary.md`

The last real browser run passed Profile load, fake-action removal, profile-save persistence at the API, membership/quota, all three direction switches, logout, `/api/me=401` after logout, and reload-to-login. Its raw report counted the expected post-logout 401s as failures, so the acceptance script was corrected to exclude only those expected responses and to wait for the initial `/api/me` response before checking the refreshed Profile UI.

The corrected script has not yet been rerun because the final logout intentionally revoked the saved test session. Final gate remains:

`PROFILE_ACTIONS_CLEANUP_NOT_VERIFIED`
