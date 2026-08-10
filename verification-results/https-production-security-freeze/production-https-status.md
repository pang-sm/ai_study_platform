# Production HTTPS status

Generated: 2026-08-10

## Final status

- `HTTPS_PRODUCTION_NOT_VERIFIED`
- `PRODUCTION_SECURITY_FREEZE_NOT_VERIFIED`
- `HTTPS_REQUIRED_BEFORE_PRODUCTION_SECURITY_FREEZE`

## Target

- Public origin: `https://101.32.190.42/`
- HTTP origin: `http://101.32.190.42/`

## Implementation and deployment evidence

- HTTPS implementation commit: `eef8cfd`
- Certbot executable-path fix: `e6e6fa8`
- External HTTPS probe and UFW handling: `65eda6b`
- Server deployment Actions: `31387119251` — success
- External public HTTPS probe Actions: `31387661640` — failed at `Verify public HTTPS reachability`

The successful server deployment passed the server-local nginx/certificate/renewal stage and activated the production Secure Cookie environment. The separate external probe is required because a localhost probe cannot establish public reachability.

## Observed network evidence

| Probe | Result |
| --- | --- |
| `http://101.32.190.42/` before deployment | `200` |
| `http://101.32.190.42/` after deployment | `308` with `Location: https://101.32.190.42/` |
| Direct `101.32.190.42:443` TCP/TLS probe | timeout |
| Normal browser navigation to `https://101.32.190.42/` | timeout; no trusted TLS page loaded |
| Public `https://101.32.190.42/api/health` probe | failed |

The remaining blocker is public TCP 443 reachability, most likely a Tencent Cloud security-group or upstream firewall rule. The deployment script opens TCP 80/443 only when host UFW is active; it cannot change a Tencent Cloud security group from the server.

## Not yet verified

Because trusted public TLS is not reachable, these checks remain blocked and are intentionally not marked as passed:

- certificate issuer, IP SAN, and browser trust
- `ai_session` observed with `Secure=true`
- fresh-context `/api/me=200` and logout `/api/me=401`
- WSS Workbench run
- mixed-content count
- Course Learning, 11408, Programming, AI Chat, Materials, Reports, Profile, Membership, Checkout, Redemption, and Admin browser regression

No private key, cookie value, token, password, or storage state is stored in this report.
