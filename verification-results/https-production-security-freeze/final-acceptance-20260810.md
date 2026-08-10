# Production Security Freeze final acceptance

Generated: 2026-08-10

## Verified production evidence

| Item | Status | Evidence |
| --- | --- | --- |
| Public TCP 443 | PASS | `Test-NetConnection 101.32.190.42 -Port 443` succeeded. |
| Trusted TLS certificate | PASS | Normal TLS validation succeeded. Certificate issuer is Let's Encrypt YE2; IP SAN contains `101.32.190.42`; validity is 2026-08-10 through 2026-08-17. |
| Browser TLS | PASS | Headless Chromium loaded `https://101.32.190.42/` with TLS validation enabled. |
| HTTP to HTTPS | PASS | `/` and `/api/health` return 308 to the matching HTTPS URL. |
| HTTPS health | PASS | `GET https://101.32.190.42/api/health` returned `200 {"status":"ok"}`. |
| `ai_session` attributes | PASS | HTTPS administrator login recorded `HttpOnly=true`, `Secure=true`, `SameSite=Lax`, `Path=/`; the shared production cookie setting also served the verified normal-user HTTPS login. No cookie value was recorded. |
| Normal authentication | PASS | HTTPS login, `/api/me=200`, and fresh-context `/api/me=200` passed before the final logout check. |
| Administrator authentication | PASS | HTTPS `/api/me=200`, `super_admin`, and fresh-context authentication passed. |
| Course Learning | PASS | Real HTTPS course UI loaded without business console or network errors. |
| 11408 | PASS | Real HTTPS 11408 home loaded without business console or network errors. |
| Programming | PASS | Real HTTPS workbench opened exercise 1734. |
| WSS runtime | PASS | `wss://101.32.190.42/code/interactive-run` opened; run exited with code 0; public tests were 3/3 and submit tests 8/8. |
| AI Chat | PASS | Real HTTPS course chat request returned 200 and rendered a response. |
| Materials | PASS | Real HTTPS materials panel and required APIs loaded. |
| Learning Report | PASS | Real HTTPS report panel and history/detail APIs loaded. |
| Profile | PASS | Profile persistence and three-direction consistency passed; original nickname was restored. |
| Admin Dashboard | PASS | Dashboard, operations dashboard, usage summary, usage trend, and permissions returned 200; no fake revenue/growth text, no console business errors, and no unexpected network failures. The page correctly displayed today's zero calls. |
| Membership | PASS | Dedicated normal QA user was created through the real `/register` UI, completed Course Learning onboarding with the free plan, and then selected a legal higher plan through the Membership UI. |
| Checkout | PASS | Real UI created pending order `24`; checkout reload preserved `pending`, mock payment completed it, and a further reload preserved `paid`. The paid Course Learning catalog reported the monthly plan with a non-empty expiry. |
| Redemption | PASS | A dedicated admin-created Course Learning monthly/30-day/one-use QA code was previewed and redeemed through the UI. Refresh and fresh-context UI login preserved the entitlement; order count stayed `0 → 0`; admin showed `1/1 exhausted`; a second preview was rejected with HTTP 400. Plaintext code and QA passwords were not persisted. |
| Mixed Content | PASS | No mixed-content error, `http://101.32.190.42` business request, or `ws://` request was observed in the HTTPS smoke flows. |
| Console | PASS | No business console errors in normal-user smoke, WSS, profile, or admin acceptance. |
| Network | PASS | No unexpected business network failures in normal-user smoke, WSS, profile, or admin acceptance. |
| Logout | PASS | `/api/logout=200`, then `/api/me=401` as the expected pass condition, followed by the login view on reload. |

## Infrastructure acceptance blocked by GitHub default-branch requirement

| Item | Status | Blocking evidence |
| --- | --- | --- |
| Live nginx `nginx -t` | NOT VERIFIED | No live SSH command was run. GitHub rejects `workflow_dispatch` for a workflow absent from the default branch. |
| Certbot/timer/renewal config/deploy hook | NOT VERIFIED | The manual-only workflow is committed on `codex/security-freeze-acceptance`, but GitHub resolves dispatchable workflows from `main`. |
| Renewal rehearsal | NOT VERIFIED | `certbot renew --dry-run` was intentionally not run outside the workflow. No production certificate state was changed. |

## Non-blocking hardening

`HSTS_NOT_ENABLED_NON_BLOCKING`: HSTS was not observed. It was intentionally not added for the IP-based production entry point.

## Final status

- `HTTPS_PRODUCTION_NOT_VERIFIED`
- `PRODUCTION_SECURITY_FREEZE_NOT_VERIFIED`

Membership, Checkout, and Redemption are complete. The only remaining mandatory evidence is the manual production SSH infrastructure acceptance. The attempted GitHub dispatch produced no run ID because the workflow is not yet on the default branch; merging it to `main` (which will invoke the repository's existing deployment workflow) requires separate authorization. No production SSH command or business deployment was performed in this acceptance run.

## Related artifacts

- `verification-results/https-production-security-freeze/wss-workbench/programming-workbench-cli-acceptance.json`
- `verification-results/profile-actions-production/profile-actions-final-acceptance.json`
- `verification-results/admin-dashboard-production/acceptance-final.json`
- `verification-results/membership-redemption-production/acceptance-final.json`
- `.github/workflows/production-security-freeze.yml` (manual-only workflow; not yet dispatchable until present on `main`)

Sensitive credentials, cookie values, tokens, and storage-state contents are not included in this report.
