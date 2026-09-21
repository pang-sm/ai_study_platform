"""Dataset provenance — WHY a recorded fact exists, carried on the fact itself.

ACCEL_PRODUCT_S10 PART F/G. A learning fact is not only what happened; it is also
*under what arrangement* it was recorded. A demo rehearsal and a real learner answering a
real question produce rows of identical shape, and nothing in the row distinguishes them.
That distinction cannot be reconstructed afterwards — it is not derivable from a timestamp,
a user id, or a session — so it has to be written down at the moment of recording, by the
only code that knows: the writer.

THE ONE RULE
------------
Only ``LEARNER`` facts may train a model or satisfy a data-readiness gate. Everything else
exists to demonstrate, to verify, or to test the product, and a model trained on it would
learn the demonstration rather than the learning.

FAIL CLOSED, IN BOTH DIRECTIONS
-------------------------------
An unrecognized origin is NOT ``LEARNER``. A NULL origin is NOT ``LEARNER``. Both are
reported as ``UNCLASSIFIED`` and counted separately, so a writer that forgets to stamp its
rows produces a visible, empty bucket instead of a silent contribution to the training set.
That is the whole reason ``LEARNER`` is stated explicitly by each writer rather than being
the column's default.

WHY THE ENVIRONMENT CHOOSES IT, AND WHY PRODUCTION REFUSES TO BE TOLD
---------------------------------------------------------------------
The demo environment is a separate deployment bound to a separate database, so the choice of
origin is a property of the PROCESS, not of a request: ``DATA_ORIGIN=DEMO`` on the demo
server's environment. Letting a request body declare its own origin would let any client
write facts that no gate would ever count, which is a data-integrity hole, not a feature.

Because that env var suppresses real data from the training set, production refuses it —
the same shape as the mock-payment gate in ``payments.registry``: an operator convenience
that is deliberately unavailable where it would be destructive.
"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger("data_plane.origin")

# A real learner's own action on the real product. The ONLY training-admissible value.
LEARNER = "LEARNER"

# Produced by the demo/acceptance seed path so the product can be shown without polluting
# the real dataset.
DEMO = "DEMO"

# Produced by a product-acceptance rehearsal that is expected to be re-runnable.
ACCEPTANCE = "ACCEPTANCE"

# Produced by the automated test suite.
TEST = "TEST"

# Produced by a back-fill that INVENTS facts rather than re-projecting recorded ones. The
# current backfill re-projects real source attempts and therefore stamps the active origin
# instead; this value exists so such a path has a correct value to use rather than reusing
# LEARNER, and it is excluded from training for the same reason as the others.
BACKFILL_SYNTHETIC = "BACKFILL_SYNTHETIC"

ALL_ORIGINS = (LEARNER, DEMO, ACCEPTANCE, TEST, BACKFILL_SYNTHETIC)

# Origins a training export or a data-readiness gate MAY count.
TRAINING_ADMISSIBLE = frozenset({LEARNER})

# Origins that must be excluded, each for its own reason.
EXCLUDED_FROM_TRAINING = frozenset({DEMO, ACCEPTANCE, TEST, BACKFILL_SYNTHETIC})

# NOT a stored value. The report bucket for rows whose origin is NULL or unrecognized.
UNCLASSIFIED = "UNCLASSIFIED"

ENV_VAR = "DATA_ORIGIN"


def normalize(origin) -> str:
    """Map a stored value onto one of the closed set, or ``UNCLASSIFIED``. Fail closed."""
    value = (origin or "").strip().upper() if isinstance(origin, str) else ""
    return value if value in ALL_ORIGINS else UNCLASSIFIED


def active_origin() -> str:
    """The origin this PROCESS stamps on the facts it records.

    Read from ``DATA_ORIGIN`` on every call rather than cached at import: the value is a
    deployment property that tests set and unset, and a cached read would make a test's
    origin leak into the next test that did not ask for it.
    """
    raw = os.getenv(ENV_VAR, "").strip().upper()
    if not raw:
        return LEARNER
    if raw not in ALL_ORIGINS:
        logger.warning("%s=%r is not a known origin; recording as UNCLASSIFIED", ENV_VAR, raw)
        return UNCLASSIFIED
    if raw != LEARNER and _production():
        logger.error("%s=%r is refused in production; recording as UNCLASSIFIED. "
                     "Demo and test data must never be written to the production database.",
                     ENV_VAR, raw)
        return UNCLASSIFIED
    return raw


def _production() -> bool:
    from payments.registry import is_production_runtime  # lazy: avoid an import cycle
    return is_production_runtime()


def stamp(payload: dict) -> dict:
    """Attach this process's active origin to a row payload. Returns the same mapping."""
    payload["data_origin"] = active_origin()
    return payload


# --------------------------------------------------------------------------- account origin
#
# THE TRUST BOUNDARY. An ACCEPTANCE account is a property of ONE account, not of a
# deployment: a production learner account used for acceptance rehearsal. The process-wide
# ``DATA_ORIGIN`` cannot express it (production refuses that variable, and rightly — a
# deployment-wide switch that suppresses every learner's data from training is destructive
# where it is wrong). So the account carries its own marker, ``users.data_origin``, which
# is server state written only through the admin-only contract
# ``PUT /admin/users/{username}/data-origin`` and is audit-logged. Nothing a client sends —
# body, header, cookie or query — can set it.
#
# THE ONE-WAY RULE. A marker may only DEMOTE admissibility: it can name an origin that is
# excluded from training, never ``LEARNER``. So the worst a mis-set or corrupted marker can
# do is withhold one account's facts from the training set; it can never admit a demo or
# test deployment's facts into it. ``ALLOWED_ACCOUNT_ORIGINS`` is exactly the excluded set.
ALLOWED_ACCOUNT_ORIGINS = EXCLUDED_FROM_TRAINING


def _resolve_marker(user) -> str | None:
    """The origin this ACCOUNT's marker names, or ``None`` when it has no usable marker."""
    raw = getattr(user, "data_origin", None)
    if isinstance(raw, str):
        marked = raw.strip().upper()
        if not marked:
            return None
        if marked in ALLOWED_ACCOUNT_ORIGINS:
            return marked
        logger.error("users.data_origin=%r is not a usable account origin; recording as "
                     "UNCLASSIFIED. An account marker may only name an origin excluded from "
                     "training.", raw)
        return UNCLASSIFIED
    return None


def origin_for_user(user) -> str:
    """The origin to stamp on facts THIS ACCOUNT produces.

    The process origin wins whenever it already says something other than ``LEARNER``: a
    demo or test deployment declares its nature once, for every account on it, and an
    account marker cannot upgrade that. Only on an otherwise-``LEARNER`` process (production
    and the default) does the account's own marker apply — which is the only way an
    acceptance account can be expressed there.

    A marker that names something unusable fails CLOSED to ``UNCLASSIFIED`` (excluded, and
    reported in its own bucket) rather than falling back to ``LEARNER``, because falling
    back would silently make a marked account's facts admissible.
    """
    process_origin = active_origin()
    if process_origin != LEARNER:
        return process_origin
    return _resolve_marker(user) or LEARNER


def origin_for_user_id(user_id, session) -> str:
    """``origin_for_user`` for a caller that holds only an id — the event producers do.

    The lookup runs in the caller's session and only when the process origin is ``LEARNER``,
    so demo/test deployments pay nothing. A failed lookup fails CLOSED to ``UNCLASSIFIED``:
    a fact wrongly withheld from training is recoverable, a fact wrongly admitted is not.
    """
    from models import User  # local import: keeps this module import-light for its callers

    process_origin = active_origin()
    if process_origin != LEARNER:
        return process_origin
    if user_id is None:
        return LEARNER
    try:
        row = session.query(User.data_origin).filter(User.id == user_id).first()
    except Exception as exc:  # noqa: BLE001 — never fail the caller's fact on this
        logger.error("account origin lookup failed for user_id=%s (%s); recording as "
                     "UNCLASSIFIED", user_id, type(exc).__name__)
        return UNCLASSIFIED
    return _resolve_marker(_RowCarrier(row[0] if row else None)) or LEARNER


class _RowCarrier:
    """Adapts a bare column value to the attribute ``_resolve_marker`` reads."""

    __slots__ = ("data_origin",)

    def __init__(self, data_origin):
        self.data_origin = data_origin


def is_training_admissible(origin) -> bool:
    return normalize(origin) in TRAINING_ADMISSIBLE


def exclusion_reason(origin) -> str | None:
    """Why a fact is excluded from training, or ``None`` when it is admissible."""
    value = normalize(origin)
    if value in TRAINING_ADMISSIBLE:
        return None
    if value == UNCLASSIFIED:
        return "DATA_ORIGIN_NOT_RECORDED"
    return f"DATA_ORIGIN_{value}"
