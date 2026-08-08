# Admin Dashboard production acceptance

Status: `ADMIN_DASHBOARD_DATA_CLEANUP_VERIFIED`

## Authentication

- Production URL: `http://101.32.190.42/`
- Unified entry: `/login`
- Final run reused the saved Playwright storage state after the prior unified login bootstrap.
- `/api/me`: `200`
- Username match: `true`
- `is_admin`: `true`
- `admin_role`: `super_admin`
- Fresh-context storage-state reload: `200`
- Auth file: `.playwright/.auth/admin-dashboard-production.json` (gitignored; not committed)
- The dedicated account `admin_acceptance` remains active for reproducible acceptance. No password, token, or cookie value is stored in this report.

## Acceptance matrix

| Item | Result | Evidence |
| --- | --- | --- |
| Admin unified login | PASS | `/login`, `/api/me=200`, `super_admin` |
| Dashboard load | PASS | 4 dashboard cards rendered |
| User metrics | PASS | API/UI total users both `165` |
| Learning metrics | PASS | API/UI total courses both `6` |
| AI metrics | PASS | `/api/admin/usage-summary=200`, today total `7` |
| Order/revenue empty state | PASS | `暂无订单数据`; no revenue card |
| No hardcoded growth | PASS | No forbidden fixed growth values in checked pages |
| Real trend chart | PASS | `/api/admin/usage-trend=200`, 7 real dates visible |
| AI estimated cost wording | PASS | `估算成本` present; `实际支出` absent |
| Console | PASS | 0 business errors |
| Network | PASS | 0 unexpected business failures |

## Admin API statuses

All checked APIs returned `200`:

- `/api/admin/dashboard`
- `/api/admin/operations-dashboard`
- `/api/admin/usage-summary`
- `/api/admin/usage-trend`
- `/api/admin/me/permissions`

Two `net::ERR_ABORTED` events occurred while navigation replaced in-flight usage requests; they were classified as expected navigation aborts. There were no unexpected business network failures and no business console errors.

## Database and deployment

- Production database was changed only to create/update the dedicated acceptance administrator.
- Backup: `/var/lib/ai_study_platform/backups/app.db.before-admin-acceptance.20260808-133405.db`
- Business cleanup deployment: commit `a5a1ca4`, Actions `31257313512`.
- Follow-up `/api/admin/usage-summary` fix: commit `b627929`, Actions `31260146912`, deployment successful.
- `/api/health`: `200`, `{"status":"ok"}`.
- No new business deployment was required for this final acceptance.

## Screenshots

- `screenshots/admin-dashboard-home.png`
- `screenshots/admin-dashboard-orders-empty.png`
- `screenshots/admin-dashboard-statistics-trend.png`
- `screenshots/admin-dashboard-ai-usage.png`
- `screenshots/admin-center-overview.png`

Machine-readable evidence: `acceptance-final.json`.
