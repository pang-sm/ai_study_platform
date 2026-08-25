# Mobile IA Stage 3 Information Architecture Report

## Final status

**MOBILE_IA_STAGE3_FAILED**

The Mobile IA implementation and Production static deployment completed, but the mandatory authenticated Production acceptance and PC ↔ Mobile mastery synchronization did not complete. The manually authenticated in-app-browser tab displayed a stale pre-deployment desktop page at `/m`; refreshing it reset browser control. A fresh browser connection then exposed no claimable authenticated tab. No session was injected, no credential was recorded, and no account data was changed.

## Modified files

- `frontend/src/mobile/MobileApp.jsx`
- `frontend/src/mobile/MobileApp.css`

## Implementation commit

- Commit: `4d1edc430bf6fc2f76bb66a49220c89daabf0e28`
- Message: `refactor(mobile): isolate learning spaces`

## Completed IA changes

1. AI history is now automatically scoped by the current learning space (`课程学习`, `11408考研`, or the dedicated `普通AI` route). The manual All/Course/11408/Normal filter bar was removed.
2. Knowledge-point Bottom Sheet now has a 70dvh maximum height, internal scrolling, and persistent bottom actions only for `AI 解释` and `保存掌握程度`.
3. The Bottom Sheet continues to use `PATCH /api/knowledge-map/progress` and only exposes server-supported states: 未掌握、薄弱、一般、掌握.
4. The Profile avatar no longer shows an edit badge; tapping it takes the user to the existing account-settings section (avatar, nickname, password, email).
5. Store entries are limited to server-backed 会员套餐、课程权益、11408套餐. The former 学科包 placeholder was removed.

## Build and lint

| Check | Result |
| --- | --- |
| `npm.cmd run build` | PASS |
| `npm.cmd exec eslint src/mobile/MobileApp.jsx` | PASS |

## Production deployment

- URL: `https://101.32.190.42/m`
- Static directory: `/var/www/ai_study_platform`
- Entry bundle: `index-CshRehbi.js`
- SHA-256: `0AED0A92DB67F9779F4A8188B655AFE0CCD03E365D0582702836C841802D24C7`
- Production HTML entry: `assets/index-CshRehbi.js`
- Public bundle HTTP status: `200`
- Backup: `/home/ubuntu/ai-study-platform-backups/mobile-ia-stage3-20260825-dist-before.tgz`

## Authenticated browser evidence

| Item | Result | Actual observation |
| --- | --- | --- |
| Manual authenticated tab claimed | PASS | Existing account session was visible and could be claimed. |
| First `/m` rendered state | FAIL | It displayed the pre-deployment desktop 编程学习 page, indicating the existing tab had loaded the previous bundle. |
| Reload into current bundle | BLOCKED | Browser control reset during reload. |
| Profile space switch | BLOCKED | Needs a stable refreshed authenticated Mobile shell. |
| AI history isolation | BLOCKED | Needs a stable refreshed authenticated Mobile shell. |
| Knowledge Sheet save | BLOCKED | Needs real course data in a stable Mobile shell. |
| PC → Mobile mastery sync | BLOCKED | Needs two stable authenticated surfaces using the same account. |
| Mobile → PC mastery sync | BLOCKED | Needs two stable authenticated surfaces using the same account. |

## Screenshot evidence

The claimed authenticated browser visibly showed the stale desktop 编程学习 layout at `/m`. Browser control reset during the required refresh, so no durable local screenshot path or post-refresh Mobile screenshot could be captured.

## Important deployment note

`frontend/src/main.jsx` was already modified and uncommitted before this task. The new bundle was built from that existing workspace state, so it includes its `/m` → `MobileApp` route logic. This task did not edit or commit `main.jsx`; its separate worktree state must be reviewed before it is committed.

