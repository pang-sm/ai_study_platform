"""Structured security audit events for learner code execution — SECURITY_S0.5.

SECURITY_S0 closed the host-RCE path but left no trace of an attempt: neither
``POST /code/projects/{id}/execute`` nor the exercise judge logged anything, so the
incident review could only say ``INSUFFICIENT_LOGGING``. These events close that
detection gap.

Two rules govern every field emitted here:

1. **Allowlist, never denylist.** A field appears in the log only because it is named
   in ``_CONTEXT_FIELDS`` below. A future caller cannot smuggle learner content into
   the log by passing an extra argument — unknown keys are rejected outright.
2. **Never log the artefact.** Submitted source, stdin, stdout/stderr, cookies,
   ``Authorization`` headers, session tokens and provider keys are code and credential
   material, and a log line is exactly the wrong place for them.

Events go to the dedicated ``security.audit`` logger as one greppable line per attempt
(``journalctl -u ai-backend | grep CODE_EXECUTION``). They deliberately do NOT go to
``admin_audit_logs``: that table is the admin console's action trail, and in the
post-S0 steady state *every* execution attempt is a denial, which would drown it.
"""
from __future__ import annotations

import logging
from contextvars import ContextVar
from typing import Any, Iterator

from core.logging import ensure_security_audit_logging

logger = ensure_security_audit_logging()

# The complete set of context a caller may bind. Nothing else is ever logged.
_CONTEXT_FIELDS = ("user", "action", "language", "resource", "request_id", "ip")

# Event identifiers. Denials are the steady state until a verified sandbox is restored.
CODE_EXECUTION_PERMITTED = "CODE_EXECUTION_PERMITTED"
CODE_EXECUTION_DENIED_SANDBOX_UNAVAILABLE = "CODE_EXECUTION_DENIED_SANDBOX_UNAVAILABLE"

SANDBOX_UNAVAILABLE = "sandbox_unavailable"

_context: ContextVar[dict[str, Any]] = ContextVar("code_execution_audit_context", default={})


class _AuditContext:
    def __init__(self, token) -> None:
        self._token = token

    def __enter__(self) -> "_AuditContext":
        return self

    def __exit__(self, *exc_info) -> bool:
        _context.reset(self._token)
        return False


def _validated(fields: dict[str, Any]) -> dict[str, Any]:
    """Reject unknown field names rather than silently dropping them.

    A typo then becomes a loud failure instead of an audit record that quietly omits
    the user it was supposed to identify.
    """
    unknown = sorted(set(fields) - set(_CONTEXT_FIELDS))
    if unknown:
        raise ValueError(f"unsupported code-execution audit fields: {unknown}")
    return {name: value for name, value in fields.items() if value not in (None, "")}


def bind_code_execution_audit(**fields: Any) -> Any:
    """Bind audit context and return a reset token.

    Use with :func:`reset_code_execution_audit` in a ``finally``. This pair exists for
    handlers that already own a ``try/finally`` and would otherwise need their whole
    body re-indented to reach the execution call.
    """
    return _context.set(_validated(fields))


def reset_code_execution_audit(token: Any) -> None:
    _context.reset(token)


def code_execution_audit_context(**fields: Any) -> _AuditContext:
    """Bind who/what for the duration of one execution attempt."""
    return _AuditContext(_context.set(_validated(fields)))


def _flat(value: Any) -> str:
    """Render one field on a single line, bounded, so the log stays parseable."""
    text = str(value).replace("\r", "\\r").replace("\n", "\\n").replace("\t", "\\t")
    return text[:200]


def _current_context() -> dict[str, Any]:
    return dict(_context.get())


def audit_code_execution(
    event: str,
    *,
    allowed: bool,
    reason: str = "",
    backend: str = "",
) -> None:
    """Emit one ``CODE_EXECUTION`` security audit event.

    Only allowlisted context is written; the caller cannot pass free-form payload.
    """
    fields = _current_context()
    parts = [f"event={event}", f"allowed={'true' if allowed else 'false'}"]
    if backend:
        parts.append(f"backend={_flat(backend)}")
    if reason:
        parts.append(f"reason={_flat(reason)}")
    for name in _CONTEXT_FIELDS:
        if name in fields:
            parts.append(f"{name}={_flat(fields[name])}")
    logger.info("CODE_EXECUTION %s", " ".join(parts))


def audit_code_execution_denied(reason: str = SANDBOX_UNAVAILABLE, *, backend: str = "") -> None:
    """Record a refusal at an entry point that enforces the policy itself.

    The WebSocket terminals check availability directly (they cannot raise an HTTP
    error mid-socket), so they call this instead of going through the raised guard.
    """
    audit_code_execution(
        CODE_EXECUTION_DENIED_SANDBOX_UNAVAILABLE, allowed=False, reason=reason, backend=backend
    )


def audit_code_execution_permitted(*, backend: str = "") -> None:
    """Record an allowed attempt at an entry point that enforces the policy itself."""
    audit_code_execution(CODE_EXECUTION_PERMITTED, allowed=True, backend=backend)
