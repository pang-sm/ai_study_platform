"""Isolated learner-code execution — SECURITY_S0B-P1.

The public surface is deliberately tiny and has no host fallback:

    backend = get_execution_backend()   # None unless the deployment opted in AND the runner is present
    if backend is None:                 # refuse the request; never run code on the host
        ...
    result = backend.run(ExecutionRequest(...))

``get_execution_backend`` returns a :class:`SandboxRunnerClient` — a thin, fail-closed
client for the separate least-privileged runner service. The web process imports no Docker
backend and holds no docker access; the hardened ``docker run`` argv lives only inside the
runner package (``core.sandbox.runner``), which the web process never loads.
"""
from __future__ import annotations

import os
import threading
from typing import Any

from core.code_execution import BACKEND_DOCKER, configured_backend
from core.config import sandbox_runner_socket
from core.sandbox.runner_client import SandboxRunnerClient
from core.sandbox.types import (
    CompileResult,
    ExecutionRequest,
    ExecutionResult,
    SourceFile,
    TestCaseResult,
    Verdict,
)

__all__ = [
    "CompileResult",
    "ExecutionRequest",
    "ExecutionResult",
    "SandboxRunnerClient",
    "SourceFile",
    "TestCaseResult",
    "Verdict",
    "get_execution_backend",
    "sandbox_preflight",
]

_client: SandboxRunnerClient | None = None
_lock = threading.Lock()


def get_execution_backend() -> SandboxRunnerClient | None:
    """Return the runner client when the deployment opted in, else ``None``.

    The opt-in (``CODE_EXECUTION_BACKEND=docker``) is checked on every call so a running
    process respects the deployment's current configuration. Constructing the client does
    not prove the runner is up — a dead socket still fails closed at run time
    (``INTERNAL_ERROR``), never on the host.
    """
    if configured_backend() != BACKEND_DOCKER:
        return None
    global _client
    if _client is None:
        with _lock:
            if _client is None:
                _client = SandboxRunnerClient()
    return _client


def sandbox_preflight() -> dict[str, Any]:
    """Report whether the sandbox is safe to enable. Read-only; runs no learner code.

    Used by the enablement gate (SECURITY_S0B §14) and the acceptance harness. A ``ready``
    of False on ANY field means execution must stay disabled.
    """
    report: dict[str, Any] = {
        "backend_configured": configured_backend(),
        "runner_socket": sandbox_runner_socket(),
        "runner_reachable": False,
        "docker_cli": None,
        "docker_daemon": False,
        "images": {},
        "missing_images": [],
        "ready": False,
    }
    if configured_backend() != BACKEND_DOCKER:
        report["reason"] = "backend_not_configured"
        return report
    if not os.path.exists(sandbox_runner_socket()):
        report["reason"] = "runner_socket_missing"
        return report
    pre = SandboxRunnerClient().preflight()
    report["runner_reachable"] = "docker_daemon" in pre
    report["docker_cli"] = pre.get("docker_cli")
    report["docker_daemon"] = bool(pre.get("docker_daemon"))
    report["images"] = pre.get("images") or {}
    report["missing_images"] = pre.get("missing_images") or []
    report["ready"] = bool(pre.get("ready"))
    if not report["ready"]:
        report["reason"] = pre.get("reason") or "runner_not_ready"
    return report
