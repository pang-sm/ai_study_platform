"""Provider/model availability health (Router V1) — runtime, in-process, NOT personal.

WHAT THIS IS
------------
The pool says which models are QUALIFIED. Health says which of them are currently WORKING.
The two are different questions, and a pool that is qualified for a capability is useless to
the learner if its provider is timing out right now.

HOW IT DECIDES
--------------
A bounded, deterministic outcome window per (provider, model):

    FAILURE_THRESHOLD consecutive failures   → DEGRADED for COOLDOWN_SECONDS
    any success                              → healthy again, window cleared

A degraded model is SKIPPED by the router (the orchestrator's existing cross-provider
fallback then picks the next qualified candidate), and the decision records which models were
skipped and why. When a cooldown expires the model is retried automatically and recovers on
its first success.

WHAT IT IS NOT
--------------
It is not personalization and not online learning from learner feedback: it carries no user
id, no learner signal and no capability preference, and nothing here writes to the pool, the
router policy or the database. Feedback never touches it (a dislike does not make a model
unavailable; a timeout does).
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

FAILURE_THRESHOLD = 3
COOLDOWN_SECONDS = 120.0
MAX_TRACKED = 64


@dataclass
class _Entry:
    consecutive_failures: int = 0
    degraded_until: float = 0.0
    last_error: str | None = None
    outcomes: list = field(default_factory=list)


class HealthRegistry:
    """Process-local availability state. Deterministic given the same outcome sequence."""

    def __init__(self, *, failure_threshold: int = FAILURE_THRESHOLD,
                 cooldown_seconds: float = COOLDOWN_SECONDS, clock=time.monotonic):
        self._lock = threading.Lock()
        self._entries: dict[tuple[str, str], _Entry] = {}
        self._failure_threshold = max(1, int(failure_threshold))
        self._cooldown_seconds = max(1.0, float(cooldown_seconds))
        self._clock = clock

    # ---- recording ----

    def record_success(self, provider: str, model: str) -> None:
        key = self._key(provider, model)
        with self._lock:
            entry = self._entries.setdefault(key, _Entry())
            entry.consecutive_failures = 0
            entry.degraded_until = 0.0
            entry.last_error = None
            entry.outcomes.append("ok")
            del entry.outcomes[:-16]

    def record_failure(self, provider: str, model: str, error: str | None = None) -> None:
        key = self._key(provider, model)
        with self._lock:
            entry = self._entries.setdefault(key, _Entry())
            entry.consecutive_failures += 1
            entry.last_error = error
            entry.outcomes.append("failed")
            del entry.outcomes[:-16]
            if entry.consecutive_failures >= self._failure_threshold:
                entry.degraded_until = self._clock() + self._cooldown_seconds
            self._evict_if_needed()

    # ---- reading ----

    def is_degraded(self, provider: str, model: str) -> bool:
        key = self._key(provider, model)
        with self._lock:
            entry = self._entries.get(key)
            if entry is None or entry.degraded_until == 0.0:
                return False
            if self._clock() >= entry.degraded_until:
                # cooldown expired → it is a candidate again (and one failure re-arms it)
                entry.degraded_until = 0.0
                entry.consecutive_failures = 0
                return False
            return True

    def snapshot(self) -> dict:
        """Observability: the current availability picture, no user data in it."""
        with self._lock:
            now = self._clock()
            return {
                f"{provider}/{model}": {
                    "consecutive_failures": entry.consecutive_failures,
                    "degraded": entry.degraded_until > now,
                    "degraded_until": (entry.degraded_until - now
                                       if entry.degraded_until > now else None),
                    "last_error": entry.last_error,
                }
                for (provider, model), entry in sorted(self._entries.items())
            }

    def reset(self) -> None:
        """Test/support helper: forget every outcome."""
        with self._lock:
            self._entries.clear()

    def describe(self) -> dict:
        """The scope of this state, stated for the operator (P5 §G).

        ``process_local`` is a FACT about the implementation, and it comes with the deployment
        requirement it implies: the platform must run ONE backend process for the availability
        picture to be complete. That is the current topology (a single systemd service behind
        one nginx upstream, the same assumption the in-process Docker semaphore and the code-run
        rate limiter already make).
        """
        snapshot = self.snapshot()
        degraded = [key for key, entry in snapshot.items() if entry["degraded"]]
        return {
            "scope": "process_local",
            "deployment_requirement": "single_backend_process",
            "failure_threshold": self._failure_threshold,
            "cooldown_seconds": self._cooldown_seconds,
            "tracked_models": len(snapshot),
            "degraded_models": degraded,
            "models": snapshot,
            "note": ("availability is a runtime signal, not personalization: it carries no "
                     "user id and is never fed by learner feedback"),
        }

    # ---- internals ----

    def _key(self, provider: str, model: str) -> tuple[str, str]:
        return ((provider or "").strip().lower(), (model or "").strip())

    def _evict_if_needed(self) -> None:
        if len(self._entries) <= MAX_TRACKED:
            return
        healthy = [key for key, entry in self._entries.items()
                   if entry.degraded_until == 0.0 and entry.consecutive_failures == 0]
        for key in healthy[:len(self._entries) - MAX_TRACKED]:
            self._entries.pop(key, None)


REGISTRY = HealthRegistry()


def registry() -> HealthRegistry:
    """The process-wide registry the router consults (one per process, like the pool)."""
    return REGISTRY
