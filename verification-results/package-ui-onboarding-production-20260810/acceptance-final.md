# Package UI and onboarding payment production acceptance

Date: 2026-08-10

Production URL: `http://101.32.190.42/`

## Result

`PACKAGE_UI_AND_ONBOARDING_PAYMENT_VERIFIED`

Business fix deployed in this acceptance: `711fc4b`

Actions run: `31349459864` — success

Health: `/api/health` returned `{"status":"ok"}`.

## Production matrix

| Item | Result | Evidence |
| --- | --- | --- |
| Authentication | PASS | Unified login/session remained usable through all flows |
| 11408 Membership / Checkout / Success | PASS | Existing production acceptance completed order #11; pending, paid, refresh and return to 11408 passed |
| Course free onboarding | PASS | New direction onboarding completed through package step; selecting free returned to the new Course Learning home |
| Programming paid onboarding | PASS | Dedicated account, programming exercise monthly plan, order #13 |
| Programming Checkout refresh | PASS | After refresh, Checkout remained open and order #13 remained pending |
| Programming payment success refresh | PASS | After simulated payment, refresh remained on paid Success with order #13 |
| Programming Success return | PASS | Returned to the new ProgrammingHome |
| Existing-user upgrade | PASS | Programming Membership monthly plan → quarterly upgrade Checkout; temporary order #14 was cancelled after verification |
| Catalog/service isolation | PASS | Programming UI showed programming-specific plan names, quotas and service direction; Course and 11408 catalogs were separately observed |
| Purple/current UI | PASS | Membership, onboarding package cards and Checkout used the current purple visual system |
| No legacy Plan/Sidebar/PackageStep for registered user | PASS | Registered-user direction switch opened the current ProgrammingHome; no legacy Plan page or PackageStep appeared |
| Membership scroll at 1366×768 | PASS | Internal scroll container reached its maximum; bottom plan actions were visible in the bottom screenshot |
| Checkout scroll at 1366×768 | PASS | Internal scroll container reached its maximum; payment/cancel actions remained in the bottom evidence |
| Success refresh at 1366×768 | PASS | Paid Success remained rendered after refresh |
| Console | PASS | No business console errors observed |
| Network | PASS | No unexpected business 4xx/5xx observed during the completed flows |

## Onboarding payment details

The first paid onboarding attempt exposed a real refresh bug: after creating a programming order and refreshing Checkout, the app returned to onboarding step 1. The failure screenshot is retained at:

`screenshots/programming-checkout-refresh-fail-before-fix.png`

Root cause: the auth bootstrap always routed a user with incomplete onboarding to step 1, even when a persisted membership Checkout context with an order id existed.

Minimal fix: `frontend/src/App.jsx` now prioritizes a persisted Checkout context during auth bootstrap and restores `membershipCheckout` before applying the incomplete-onboarding route.

After deployment, the same business flow was repeated with a dedicated newly registered account:

1. Programming onboarding → package step → paid monthly plan.
2. Created order `#13`, service `programming`, target plan `programming_monthly`, amount `¥9.00`, status `pending`.
3. Refreshed Checkout; order `#13` remained pending.
4. Simulated payment; order became paid and the Success view displayed the programming plan and order details.
5. Refreshed Success; the paid view remained present.
6. Returned to the new ProgrammingHome.

The free onboarding flow was also completed for Course Learning; choosing the free plan did not create a fake payment order and returned directly to the Course Learning home.

## Console and network

The only repeated browser noise was third-party Statsig telemetry timeout output for `https://ab.chatgpt.com/v1/initialize` and `https://ab.chatgpt.com/v1/rgstr`. It did not block any business flow and is not counted as a business error.

No password, cookie, token, or authentication storage value is included in this report.

## Screenshots

Directory: `verification-results/package-ui-onboarding-production-20260810/screenshots/`

- `11408-membership-1366x768.png`
- `programming-membership-1366x768.png`
- `programming-membership-bottom-1366x768.png`
- `programming-onboarding-checkout-1366x768-after-fix.png`
- `programming-checkout-bottom-1366x768.png`
- `programming-onboarding-success-1366x768.png`
- `programming-onboarding-success-refresh-1366x768.png`
- `programming-checkout-refresh-fail-before-fix.png`

## Deployment

- Business commit: `711fc4b` (`fix: restore onboarding checkout after auth bootstrap`)
- Actions: `31349459864`, success
- `/api/health`: 200 / `status=ok`
- Python compile: PASS
- pytest: 18 passed
- Frontend build: PASS
- No real payment provider was added.

No further business deployment is required for this acceptance.
