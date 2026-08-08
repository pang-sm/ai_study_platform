# P2 Scroll and Membership Commercialization V1 Verification

Status: `MEMBERSHIP_COMMERCIALIZATION_V1_NOT_VERIFIED`

## Scope

- Page scroll completeness for the four required desktop viewports.
- One direction-specific membership catalog for `exam_11408`, `course_learning`, and `programming`.
- Server-created pending orders, mock payment, membership activation, expiry/reminder behavior, and upgrade-only rules.
- No real payment provider, WeChat Pay, Alipay, or production payment callback was added.

## Implemented

- Added the direction-specific plan catalog and server-side rank, price, quota, duration, expiry, and service-key rules.
- Added `MembershipOrder` persistence and mock checkout endpoints.
- Reused `UserServiceMembership` for activation and effective-plan resolution.
- Routed paid onboarding choices through the unified Checkout page. Onboarding first saves the basic completed state; a paid selection then creates a mock order and activates the selected direction only after payment.
- Replaced fixed plan arrays in the course plan and 11408 plan detail pages with `/membership/catalog` data.
- Added the checkout notice that the environment is simulated and does not create a real charge.

## Local browser evidence

Flow: course onboarding -> course details -> quarterly plan -> Checkout -> create mock order -> mock pay -> course home -> profile -> refresh.

- The Checkout screen showed the server catalog price and duration for the quarterly course plan.
- The order changed from `pending` to `paid` through the backend endpoint.
- The course profile showed `季度学习包`, the server quota, and the plan remained after a full browser reload.
- The 11408 home reached the document bottom at 1366x768, 1440x900, 1536x864, and 1920x1080.
- Course knowledge, course report, membership, and checkout scroll containers reached their measured bottoms at 1366x768.
- Local backend tests: 17 passed.
- Frontend build: passed.

## Production state

Deployment completed successfully through Actions run `31262840479` for commit `8dbc691`. `http://101.32.190.42/api/health` returned HTTP 200.

The existing admin storage state remained valid. A production headless browser check opened the unified site and reached the Admin Dashboard with zero business console errors and zero unexpected API failures. The deployed page did not show the removed fixed growth percentages. Evidence: `production-admin-1366x768.png`.

The ordinary member storage state was expired: production `/api/me` returned HTTP 401 and the page correctly rendered the login screen. The in-app Browser also timed out while opening the production page, so it was not used as evidence of a passing member flow. The project Playwright fallback was used only to document this authentication blocker and the valid admin state; it did not fabricate a session or bypass login.

Therefore the member-side production flow remains not verified. The Checkout, paid persistence after reload, expiry display, quota consistency, reminder, and member scroll checks must be rerun with a valid member test session before changing the final status to `MEMBERSHIP_COMMERCIALIZATION_V1_VERIFIED`.

## Evidence

- `verification-results/p2-scroll-membership-v1/profile-11408-1366x768.png`
- `verification-results/p2-scroll-membership-v1/11408-home-1920x1080.png`
- `verification-results/p2-scroll-membership-v1/production-1366x768.png`
- `verification-results/p2-scroll-membership-v1/production-admin-1366x768.png`

No password, token, Cookie value, or payment credential is stored in this report.
