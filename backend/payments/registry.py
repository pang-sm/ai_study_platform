"""Payment provider selection and the mock-payment policy — SECURITY_S2A.

The mock provider settles an order without any money changing hands. Whether it may do so is a
security decision, so it is opt-IN: only an environment named explicitly below may use it.
"""
import os

from .mock import MockPaymentProvider

PRODUCTION_ENVIRONMENTS = ("production", "prod")

# The ONLY environments in which the mock provider may settle an order. Matched exactly after
# trimming and lower-casing — a named allowlist, never a prefix or "production-like" heuristic,
# because a fuzzy match is how a typo becomes a free membership.
MOCK_PAYMENT_ENVIRONMENTS = ("local", "test", "acceptance")


def _app_env() -> str:
    """The normalized ``APP_ENV``, or ``""`` when it is unset or blank."""
    return (os.getenv("APP_ENV") or "").strip().lower()


def is_production_runtime() -> bool:
    return _app_env() in PRODUCTION_ENVIRONMENTS


def is_mock_payment_allowed() -> bool:
    """Whether the mock provider may mark an order paid in this process.

    SECURITY_S2A — this used to be opt-OUT: it read ``os.getenv("APP_ENV", "local")`` and
    accepted the empty string, so a deployment that forgot to set ``APP_ENV``, set it blank, or
    mistyped it got the mock provider enabled. Any authenticated learner could then pay an
    order and activate a paid membership for free.

    Allowed: exactly ``local``, ``test`` and ``acceptance``. ``acceptance`` is kept because the
    authenticated end-to-end harness settles orders as part of its rehearsal.
    Denied: production, and everything else — unset, empty, whitespace-only, unexpected case,
    or a typo.

    Production is checked first so that adding a name to the allowlist by mistake still cannot
    open the mock provider in production: the two predicates here can never disagree.
    """
    if is_production_runtime():
        return False
    return _app_env() in MOCK_PAYMENT_ENVIRONMENTS


def get_payment_provider():
    # Real adapters are deliberately opt-in additions once an approved merchant
    # account and sandbox credentials exist. Never infer one from a secret.
    configured = os.getenv("PAYMENT_PROVIDER", "mock").strip().lower()
    if configured == "mock":
        return MockPaymentProvider()
    raise RuntimeError("No approved payment provider adapter is configured")
