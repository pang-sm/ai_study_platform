"""Shared adapter plumbing: outcome accounting + the fail-safe wrapper."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable

logger = logging.getLogger("learning.practice")


@dataclass
class MirrorOutcome:
    """What one mirror call did. Mirrors are counted, never silent."""

    mirrored: int = 0        # canonical attempts newly created
    deduped: int = 0         # already present with an identical fact
    conflicts: int = 0       # same source identity, different fact → refused
    failed: int = 0          # mirror could not complete
    reason: str | None = None
    detail: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.failed == 0 and self.conflicts == 0

    def to_dict(self) -> dict:
        return {
            "mirrored": self.mirrored,
            "deduped": self.deduped,
            "conflicts": self.conflicts,
            "failed": self.failed,
            "reason": self.reason,
        }


def safe_mirror(name: str, source_type: str, source_id, fn: Callable[[], MirrorOutcome],
                *, db=None) -> MirrorOutcome:
    """Run a mirror, absorbing every failure.

    The caller's durable legacy row is already committed; a canonical-mirror problem
    must not turn a successful submission into an error for the learner. The failure
    is logged with ids/types only (never answers or code) and the canonical row stays
    recoverable via backfill because its identity is deterministic.
    """
    try:
        outcome = fn()
        if outcome.conflicts:
            logger.warning(
                "practice.legacy_mirror_conflict adapter=%s source_type=%s source_id=%s "
                "conflicts=%s", name, source_type, source_id, outcome.conflicts)
        return outcome
    except Exception as exc:  # noqa: BLE001 — mirror failure must not fail the request
        logger.warning(
            "practice.legacy_mirror_failed adapter=%s source_type=%s source_id=%s "
            "error=%s", name, source_type, source_id, type(exc).__name__)
        if db is not None:
            try:
                db.rollback()
            except Exception:  # noqa: BLE001 — nothing further we can safely do
                pass
        return MirrorOutcome(failed=1, reason=type(exc).__name__)
