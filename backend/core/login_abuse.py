"""Password-login abuse protection — SECURITY_S2B.

``POST /login`` accepted unlimited guesses: nothing counted failures, so a single client
could brute-force one password, or walk a long list of accounts, as fast as the network
allowed. The only cost to the attacker was the bcrypt work the server did for them.

Two independent dimensions must both admit a request:

* **source** — the client IP, throttling one host that sprays many accounts;
* **identifier** — the account (or the literal string, when no account matches), throttling
  many hosts that converge on one account.

Neither dimension is sufficient alone. A per-IP cap is defeated by a botnet; a per-account
cap is defeated by spraying one guess across thousands of accounts. Both are keyed here, and
a request is refused if *either* is over its budget.

Four rules shape the policy:

1. **No permanent lock.** Every counter is a sliding window: a failure stops counting once it
   ages out, so pressure decays on its own and no account can be locked indefinitely. The
   window *is* the backoff — the more failures inside it, the longer until enough of them
   expire for admission to resume.
2. **A wrong guess and an unknown account are indistinguishable.** Both are recorded the same
   way, both are refused by the same predicate with the same public response, and neither
   writes anything that would tell the two apart.
3. **The password is never a key and never a log field.** The identifier dimension is keyed by
   a digest of the normalized identifier, and no credential material reaches the audit log.
4. **Process-local state.** Counters live in this process, matching the existing code-run
   limiter and the single-worker deployment. See the module note at the bottom.

Correctness under the deployment's reverse proxy depends on getting the *real* client address,
which this module refuses to guess, so the default trusts no forwarded header at all. That
default is nonetheless effective in production, and the reason is worth recording:

* nginx terminates TLS on the same host and proxies to ``127.0.0.1:8000``, setting
  ``X-Real-IP $remote_addr`` and ``X-Forwarded-For $proxy_add_x_forwarded_for``
  (``deploy/nginx-ai-study-platform.conf.example``);
* uvicorn runs with its default ``proxy_headers=True`` and the default trusted-proxy set
  (loopback only — the deployment never sets ``FORWARDED_ALLOW_IPS``), so it rewrites the
  request's client address from that header.

By the time a request reaches this module, ``request.client.host`` is therefore already the
real client, and no header needs to be trusted here. The evidence is the production access
log, which records external addresses (``202.119.48.85``) rather than the proxy's loopback
address. The opt-in in :func:`resolve_client_ip` exists only for a deployment that turns
uvicorn's own proxy handling off.
"""
from __future__ import annotations

import hashlib
import os
import threading
import time
from collections import deque
from collections.abc import Mapping
from dataclasses import dataclass
from ipaddress import ip_address

from core.logging import ensure_security_audit_logging

logger = ensure_security_audit_logging()

# ── audit events ────────────────────────────────────────────────────────────
# Emitted on the dedicated ``security.audit`` logger, one greppable line per attempt,
# following the convention established by core.security_audit.
LOGIN_FAILED = "LOGIN_FAILED"
LOGIN_RATE_LIMITED = "LOGIN_RATE_LIMITED"
LOGIN_SUCCEEDED = "LOGIN_SUCCEEDED"

# ── public refusal ──────────────────────────────────────────────────────────
RATE_LIMITED_STATUS = 429
RATE_LIMITED_CODE = "login_rate_limited"
RATE_LIMITED_MESSAGE = "登录尝试过于频繁，请稍后再试。"

# ── policy ──────────────────────────────────────────────────────────────────
# The identifier budget is deliberately small: a learner mistyping a password twice is
# unaffected, while an online guessing attack gets six tries per five minutes per account.
# The source budget is deliberately generous by comparison, because one source address is
# routinely shared by a whole campus or office — the identifier dimension is what stops
# brute force, and the source dimension only has to stop bulk scanning.
IDENTIFIER_WINDOW_SECONDS = 300
IDENTIFIER_MAX_FAILURES = 5
SOURCE_WINDOW_SECONDS = 600
SOURCE_MAX_FAILURES = 40

# Extra wait applied once a budget is exhausted. Each *episode* of exhaustion doubles it, and
# it is capped at the window, so repeat abuse earns at most the window and never more.
BACKOFF_BASE_SECONDS = 30

# Hard bound on tracked keys. A client that walks a huge list of never-seen identifiers
# would otherwise grow this map without limit; the oldest entries are dropped past the cap.
MAX_TRACKED_KEYS = 20_000

CLIENT_IP_HEADER_ENV = "LOGIN_CLIENT_IP_HEADER"
TRUSTED_PROXIES_ENV = "LOGIN_TRUSTED_PROXY_IPS"

# nginx is reached over loopback in this deployment, so loopback is the only address that may
# act as a proxy by default. Widening this is an explicit deployment decision.
_DEFAULT_TRUSTED_PROXIES = "127.0.0.1,::1"

# The forwarded headers this module knows how to read, and only when named explicitly.
_FORWARDED_HEADER_MODES = frozenset({"x-real-ip", "x-forwarded-for"})

SCOPE_IDENTIFIER = "identifier"
SCOPE_SOURCE = "source"

UNKNOWN_IP = "unknown"


@dataclass(frozen=True)
class LoginAttemptDecision:
    """Whether a login attempt may proceed, and if not, why and for how long."""

    allowed: bool
    scope: str = ""
    retry_after: int = 0


# ── state (PROCESS_LOCAL) ───────────────────────────────────────────────────
_lock = threading.Lock()
_failures: dict[tuple[str, str], deque[float]] = {}
_last_touched: dict[tuple[str, str], float] = {}
# Times at which each bucket ran out of budget. Refused attempts are deliberately NOT
# recorded as failures — if they were, an attacker could hold a victim's account closed
# forever simply by continuing to knock, because every refused request would push the
# window forward. Recording only the *episodes* means the escalation can advance no faster
# than the bucket refills, which is what keeps the lockout bounded.
_exhaustions: dict[tuple[str, str], deque[float]] = {}

# The escalation stops here: at 30s, 60s, 120s, 240s, 300s (the window), so no amount of
# sustained abuse can outlast the evidence the refusal was based on.
_BACKOFF_MAX_STEPS = 4


def reset_login_abuse_state() -> None:
    """Drop all counters. For tests and for an explicit operator reset."""
    with _lock:
        _failures.clear()
        _last_touched.clear()
        _exhaustions.clear()


# ── keys ────────────────────────────────────────────────────────────────────
def normalize_login_identifier(raw: str | None) -> str:
    """The value the identifier budget is keyed on.

    ``/login`` accepts either an exact username or a verified email, and matched usernames
    case-sensitively while emails were matched case-insensitively. The limiter folds case for
    both: a case-sensitive key would let an attacker spend a fresh budget on every
    capitalization of the same target.
    """
    return (raw or "").strip().casefold()


def identifier_digest(normalized: str) -> str:
    """A stable, non-reversible handle for the audit log.

    The digest is truncated: it exists to correlate events for one identifier across lines,
    not to be reversed. Nothing that is not already in the request appears here.
    """
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def _normalize_ip(value: str | None) -> str | None:
    try:
        return str(ip_address((value or "").strip()))
    except ValueError:
        return None


def _trusted_proxies() -> frozenset[str]:
    raw = os.getenv(TRUSTED_PROXIES_ENV)
    source = _DEFAULT_TRUSTED_PROXIES if raw is None else raw
    parsed = {_normalize_ip(item) for item in source.split(",")}
    parsed.discard(None)
    # Loopback can never be widened away: it is the deployment's own proxy hop.
    parsed.add("127.0.0.1")
    parsed.add("::1")
    return frozenset(parsed)


def _forwarded_ip(headers: Mapping[str, str], mode: str) -> str | None:
    if mode == "x-real-ip":
        return _normalize_ip(headers.get("x-real-ip"))

    # ``X-Forwarded-For`` is a chain that each hop appends to, and a client is free to send a
    # forged prefix. Only the entry written by the proxy immediately in front of us is
    # trustworthy, and that is the rightmost one — so the list is read backwards and the
    # first well-formed address wins.
    chain = (headers.get("x-forwarded-for") or "").split(",")
    for entry in reversed(chain):
        resolved = _normalize_ip(entry)
        if resolved:
            return resolved
    return None


def resolve_client_ip(peer_host: str | None, headers: Mapping[str, str]) -> str | None:
    """The address to charge for this request, or ``None`` when none can be trusted.

    ``None`` means "this deployment cannot tell clients apart", which disables the source
    dimension rather than collapsing every caller into one bucket — a single shared bucket
    would let one attacker spend the whole budget and lock out everyone else.

    In production the socket peer already *is* the real client, because uvicorn translates
    nginx's forwarded header before the application sees the request (see the module
    docstring); that path needs no configuration and is what the deployment uses.

    A forwarded header is read here only as a fallback, and only when the operator has named it
    in ``LOGIN_CLIENT_IP_HEADER`` *and* the request arrived from a trusted proxy address.
    """
    peer = (peer_host or "").strip()
    trusted = _trusted_proxies()
    mode = (os.getenv(CLIENT_IP_HEADER_ENV) or "").strip().lower()

    peer_is_proxy = _normalize_ip(peer) in trusted if peer else False

    if mode in _FORWARDED_HEADER_MODES and peer and peer_is_proxy:
        forwarded = _forwarded_ip(headers, mode)
        # A forwarded address that is itself a proxy tells us nothing about the client.
        if forwarded and forwarded not in trusted:
            return forwarded

    if not peer:
        return None
    if peer_is_proxy:
        return None
    return peer


# ── policy evaluation ───────────────────────────────────────────────────────
def _dimensions(ip: str | None, identifier: str) -> list[tuple[str, str, int, int]]:
    dimensions = [
        (SCOPE_IDENTIFIER, identifier, IDENTIFIER_WINDOW_SECONDS, IDENTIFIER_MAX_FAILURES),
    ]
    if ip:
        dimensions.append((SCOPE_SOURCE, ip, SOURCE_WINDOW_SECONDS, SOURCE_MAX_FAILURES))
    return dimensions


def _live(bucket_key: tuple[str, str], now: float, window: int):
    failures = _failures.get(bucket_key)
    if failures is None:
        failures = deque()
        _failures[bucket_key] = failures
    cutoff = now - window
    while failures and failures[0] <= cutoff:
        failures.popleft()
    exhaustions = _exhaustions.get(bucket_key)
    if exhaustions is not None:
        while exhaustions and exhaustions[0] <= cutoff:
            exhaustions.popleft()
        if not exhaustions:
            _exhaustions.pop(bucket_key, None)
    _last_touched[bucket_key] = now
    return failures


def _evict_if_needed() -> None:
    """Bound the map. Runs under the lock, on the write path only."""
    if len(_failures) <= MAX_TRACKED_KEYS:
        return

    def _drop(bucket_key: tuple[str, str]) -> None:
        _failures.pop(bucket_key, None)
        _last_touched.pop(bucket_key, None)
        _exhaustions.pop(bucket_key, None)

    # Empty buckets first — they hold no evidence and are the common case for a spray.
    for bucket_key in [k for k, v in _failures.items() if not v]:
        _drop(bucket_key)
        if len(_failures) <= MAX_TRACKED_KEYS:
            return
    # Still over: drop the least recently exercised buckets.
    stale = sorted(_last_touched.items(), key=lambda item: item[1])
    for bucket_key, _touched in stale[: len(_failures) - MAX_TRACKED_KEYS]:
        _drop(bucket_key)


def backoff_floor_seconds(episodes: int, window: int) -> int:
    """The minimum wait a bucket that has run dry ``episodes`` times must serve.

    Doubles per episode and stops at the dimension's own window, so the escalation can never
    outlive the failures it was derived from.
    """
    steps = min(max(0, episodes - 1), _BACKOFF_MAX_STEPS)
    return min(window, BACKOFF_BASE_SECONDS * (2 ** steps))


def _retry_after(
    failures: deque[float], exhaustions: deque[float], now: float, window: int, limit: int
) -> int:
    """Seconds until this dimension would admit a request again.

    Two clocks contribute, and the longer one wins:

    * when a slot actually frees — admission needs the count below ``limit``, so enough of the
      oldest failures must age out first;
    * the escalation floor — a bucket that keeps running dry waits progressively longer than
      the bare window arithmetic would require.

    Both are capped at the window, so the refusal always expires together with the evidence
    behind it. That cap is what keeps this a throttle rather than a lock.
    """
    over = max(0, len(failures) - limit)
    need_to_expire = over + 1
    if need_to_expire <= len(failures):
        wait = (failures[need_to_expire - 1] + window) - now
    else:
        wait = float(window)

    floor = backoff_floor_seconds(len(exhaustions), window)
    return max(1, int(min(window, max(wait, floor))))


def check_login_attempt(*, ip: str | None, identifier: str) -> LoginAttemptDecision:
    """Refuse when either dimension is exhausted. Reads only; never records a failure."""
    now = time.monotonic()
    with _lock:
        for scope, key, window, limit in _dimensions(ip, identifier):
            bucket_key = (scope, key)
            failures = _live(bucket_key, now, window)
            if len(failures) >= limit:
                retry_after = _retry_after(
                    failures, _exhaustions.get(bucket_key, deque()), now, window, limit
                )
                return LoginAttemptDecision(allowed=False, scope=scope, retry_after=retry_after)
    return LoginAttemptDecision(allowed=True)


def record_login_failure(*, ip: str | None, identifier: str) -> None:
    """Charge one failed attempt to both dimensions.

    A failure that takes a bucket to its limit also records an *episode*, which is what the
    escalation counts. Only the failure that exhausts the budget can do this: once the budget
    is gone the caller is refused before any credential work, so a knocked-on window cannot
    push its own expiry further out.
    """
    now = time.monotonic()
    with _lock:
        for scope, key, window, limit in _dimensions(ip, identifier):
            bucket_key = (scope, key)
            failures = _live(bucket_key, now, window)
            failures.append(now)
            if len(failures) >= limit:
                _exhaustions.setdefault(bucket_key, deque()).append(now)
        _evict_if_needed()


def record_login_success(*, ip: str | None, identifier: str) -> None:
    """Release the identifier budget on a correct password.

    The owner proving the password clears the pressure on their own account, so a mistyped
    password never accumulates against someone who can obviously sign in.

    The source budget is deliberately NOT cleared: an attacker who owns one valid account
    could otherwise reset their whole host's abuse history by signing into it, and bulk
    scanning would cost nothing. A successful login is evidence about one identifier, not
    about the source.
    """
    del ip  # accepted for symmetry with record_login_failure; intentionally unused
    with _lock:
        bucket_key = (SCOPE_IDENTIFIER, identifier)
        _failures.pop(bucket_key, None)
        _last_touched.pop(bucket_key, None)
        # The escalation goes with the failures: an account that has just proved its password
        # starts from a clean floor, not from however many times it was attacked.
        _exhaustions.pop(bucket_key, None)


# ── audit log ───────────────────────────────────────────────────────────────
def _flat(value: object) -> str:
    """One bounded, single-line field, so a log line stays parseable."""
    text = str(value).replace("\r", "\\r").replace("\n", "\\n").replace("\t", "\\t")
    return text[:200]


def _emit(event: str, **fields: object) -> None:
    parts = [f"event={event}"]
    for name, value in fields.items():
        if value in (None, ""):
            continue
        parts.append(f"{name}={_flat(value)}")
    logger.info("LOGIN %s", " ".join(parts))


def audit_login_failed(*, identifier_digest: str, ip: str | None) -> None:
    """One refused set of credentials.

    ``reason`` is fixed at ``invalid_credentials`` for both an unknown account and a wrong
    password: a log that distinguished them would be a list of who has an account here.
    """
    _emit(LOGIN_FAILED, reason="invalid_credentials", identifier=identifier_digest, ip=ip or UNKNOWN_IP)


def audit_login_rate_limited(
    *, scope: str, identifier_digest: str, ip: str | None, retry_after: int
) -> None:
    _emit(
        LOGIN_RATE_LIMITED,
        scope=scope,
        identifier=identifier_digest,
        ip=ip or UNKNOWN_IP,
        retry_after=retry_after,
    )


def audit_login_succeeded(*, user: str, ip: str | None) -> None:
    _emit(LOGIN_SUCCEEDED, user=user, ip=ip or UNKNOWN_IP)
