"""Legacy → Practice Core adapters.

Each adapter takes an already-committed legacy row and mirrors it into the canonical
practice spine. The legacy table stays the domain source of truth during the
compatibility window; the canonical rows are the unified learning representation.

Mirroring is FAIL-SAFE and never fatal:
  * the legacy write has already committed, so a mirror failure can never lose it;
  * the failure is logged as ``legacy_mirror_failed`` (observable);
  * because practice identity is deterministic, the canonical row can be recovered
    later by re-running the backfill (recoverable / backfillable).

No adapter ever writes to a legacy table.
"""
from .base import MirrorOutcome, safe_mirror  # noqa: F401

__all__ = ["MirrorOutcome", "safe_mirror"]
