# Admin Dashboard data authenticity audit

Status: `ADMIN_DASHBOARD_DATA_CLEANUP_NOT_VERIFIED`

## Static audit

| Area | Before | Data source | Final handling |
| --- | --- | --- | --- |
| User total | Database value, but inactive/deleted scope was inconsistent | `/api/admin/dashboard`, `User` | Count non-deleted registered users |
| Active users | Distinct AI-log users without a consistent account-state filter | `/api/admin/dashboard`, `AiUsageLog` joined to `User` | Today's distinct AI-active non-deleted, active users |
| New users | Real `created_at` aggregation with deleted-account leakage risk | `/api/admin/operations-dashboard`, `User.created_at` | Non-deleted users, today's count and last 7 calendar days |
| Learning/content | Database counts with generic comparison copy | Dashboard and operations APIs | Real material, course, knowledge-point, task, question, and AI-log counts |
| Orders | No real order/payment source; old card looked like a metric | No order model/API | Metric card removed; order page is an explicit “not connected” empty state |
| Revenue | Hardcoded zero field; no payment source | No order/payment/revenue model/API | Revenue card removed; no payment system added |
| User trend | Fixed comparison percentages in `AdminDashboard` | Frontend constants | Removed; real date-bucket trend remains |
| AI trend | Real AI usage logs | `/api/admin/usage-trend`, `/api/admin/usage-summary` | Retained; empty data renders as empty state |
| Plan distribution | Real DB aggregation with deleted-account scope risk | `User.plan` | Non-deleted users with consistent scope |

## Removed fake data

- Removed fixed growth text: `12.5%`, `8.3%`, `15.7%`, `9.4%`, `4.6%`, and `11.3%`.
- Removed the AdminDashboard order-total and total-revenue cards.
- Removed `total_orders` and `total_revenue` from `/api/admin/dashboard`.
- Replaced unreachable legacy “较昨日” fixed comparison copy with database-statistics wording.

No order table, payment flow, payment callback, or revenue system was added.

## Real metrics

- `total_users` → `/api/admin/dashboard` → `User.is_deleted = 0`.
- `active_users_today` → `/api/admin/dashboard` → distinct `AiUsageLog.username` joined to active, non-deleted `User` rows for the current UTC day.
- `today_new_users` → `/api/admin/operations-dashboard` → non-deleted `User.created_at` from the current UTC day.
- `users_7d` → `/api/admin/operations-dashboard` → non-deleted `User.created_at` grouped by seven calendar days.
- `total_materials` → study materials where `is_deleted = false`.
- `total_courses` → union of non-empty subjects in non-deleted materials and non-empty knowledge-point course IDs.
- AI counts and trends → successful `AiUsageLog` rows; token totals are sums of recorded estimated tokens.
- Estimated AI cost → model/token aggregation with explicit “estimated” wording; this is not revenue.
- Plan distribution → non-deleted `User.plan` aggregation.

## Static scan residuals

- No `12.5`, `total_orders`, or `total_revenue` remains in the AdminDashboard/AdminCenter production statistics.
- Input `placeholder` attributes remain as legitimate form guidance.
- `mock` fallback code remains in the course/exam AI generation path, outside the admin metrics scope; it is not displayed as an admin statistic.
- `8.3` occurrences outside admin are course chapter identifiers/catalog scripts, not fake dashboard metrics.

## Validation

| Check | Result |
| --- | --- |
| Python compile | PASS |
| Backend tests | PASS — 14 passed |
| Frontend build | PASS |
| `/api/health` | PASS — HTTP 200, `{"status":"ok"}` |
| Admin login | NOT VERIFIED — no administrator auth state available |
| Admin dashboard UI | NOT VERIFIED — browser remained on the login page |
| Admin Console/Network | NOT VERIFIED — dashboard was not reached |

## Production blocker

The production URL `http://101.32.190.42/` loaded the login page in the available browser session. Only a regular Workbench auth state was present locally; no administrator credentials or administrator storage state was available. No credentials were guessed or submitted. Therefore the final production status remains `ADMIN_DASHBOARD_DATA_CLEANUP_NOT_VERIFIED`.

## Files changed

- `backend/main.py`
- `frontend/src/components/AdminDashboard.jsx`
- `frontend/src/components/AdminCenter.jsx`
