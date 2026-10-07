"""Secure code execution policy — SECURITY_S0.

USER-CONTROLLED CODE MUST NEVER EXECUTE ON THE HOST.

Every path that compiles or runs learner-submitted code passes through this module
before it may spawn a process. The default is fail closed: unless a deployment has
explicitly opted in to a verified sandbox backend, execution is refused with the
stable ``code_execution_unavailable`` result.

Having a ``docker`` binary on PATH is deliberately NOT sufficient. Treating the mere
presence of such a binary as "a sandbox is available" would let an unrelated host
package install silently re-open user code execution. The opt-in is the deployment
variable ``CODE_EXECUTION_BACKEND``, and availability is proven only by the runner
socket — never by a binary on PATH.

SECURITY_S0B-P1: the web process holds NO docker access at all. Learner code is executed
only by a separate least-privileged runner (`zhixue-sandbox`, rootless Docker) reached
over a Unix-domain socket. Availability is therefore proven by the runner's socket, never
by a `docker` binary on PATH.
"""
from __future__ import annotations

import os

from fastapi import HTTPException

from core.config import sandbox_runner_socket
from core.security_audit import (
    CODE_EXECUTION_DENIED_SANDBOX_UNAVAILABLE,
    CODE_EXECUTION_PERMITTED,
    SANDBOX_UNAVAILABLE,
    audit_code_execution,
)

CODE_EXECUTION_BACKEND_ENV = "CODE_EXECUTION_BACKEND"

BACKEND_DISABLED = "disabled"
BACKEND_DOCKER = "docker"

# Only backends whose isolation has been independently verified belong in this set.
# Restoring user code execution requires an explicit deployment change AND a verified
# sandbox (see SECURITY_S0B).
_SANDBOX_BACKENDS = frozenset({BACKEND_DOCKER})

UNAVAILABLE_CODE = "code_execution_unavailable"
UNAVAILABLE_MESSAGE = "代码运行服务暂时不可用，请稍后再试。"


def configured_backend() -> str:
    """The explicitly configured backend; absent or unrecognised values mean disabled."""
    raw = (os.getenv(CODE_EXECUTION_BACKEND_ENV) or "").strip().lower()
    return raw if raw in ({BACKEND_DISABLED} | set(_SANDBOX_BACKENDS)) else BACKEND_DISABLED


def is_secure_code_execution_available() -> bool:
    """True only when the sandbox backend is explicitly enabled AND its runner is present.

    The web process has no docker binary and no docker access; the ONLY evidence a sandbox
    exists is the runner's Unix-domain socket. A leftover ``docker`` binary on PATH must
    never re-open execution (the exact S0 incident class).
    """
    if configured_backend() not in _SANDBOX_BACKENDS:
        return False
    return os.path.exists(sandbox_runner_socket())


def code_execution_unavailable_detail() -> dict:
    """Stable machine-readable refusal. Never exposes sandbox internals."""
    return {"code": UNAVAILABLE_CODE, "message": UNAVAILABLE_MESSAGE}


def require_secure_code_execution() -> None:
    """Refuse learner code execution unless a verified sandbox may run it.

    Every decision is written to the security audit log (SECURITY_S0.5) using the
    context bound by the calling entry point. The audit record is emitted here rather
    than at each call site so an entry point cannot execute without being recorded.

    Raises:
        HTTPException: 503 with the stable ``code_execution_unavailable`` detail.
    """
    backend = configured_backend()
    if is_secure_code_execution_available():
        audit_code_execution(CODE_EXECUTION_PERMITTED, allowed=True, backend=backend)
        return
    audit_code_execution(
        CODE_EXECUTION_DENIED_SANDBOX_UNAVAILABLE,
        allowed=False,
        reason=SANDBOX_UNAVAILABLE,
        backend=backend,
    )
    raise HTTPException(status_code=503, detail=code_execution_unavailable_detail())
