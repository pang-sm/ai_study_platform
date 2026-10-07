"""Isolated learner-code execution — SECURITY_S0B.

The public surface is deliberately tiny and has no host fallback:

    backend = get_execution_backend()   # None unless the deployment opted in AND docker is usable
    if backend is None:                 # refuse the request; never run code on the host
        ...
    result = backend.run(ExecutionRequest(...))

``get_execution_backend`` never returns a host backend — if the opt-in is absent, the
daemon is unreachable, or a pinned image is missing, it returns ``None`` and the
caller must fail closed. This is the single place a caller learns whether isolation
is possible.
"""
from __future__ import annotations

import shutil
import threading
from typing import Any

from core.code_execution import BACKEND_DOCKER, configured_backend
from core.sandbox.docker_backend import DockerExecutionBackend
from core.sandbox.limits import IMAGES
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
    "DockerExecutionBackend",
    "ExecutionRequest",
    "ExecutionResult",
    "SourceFile",
    "TestCaseResult",
    "Verdict",
    "get_execution_backend",
    "sandbox_preflight",
]

_backend: DockerExecutionBackend | None = None
_lock = threading.Lock()


def get_execution_backend() -> DockerExecutionBackend | None:
    """Return the Docker backend when the deployment opted in, else ``None``.

    The opt-in (``CODE_EXECUTION_BACKEND=docker``) is checked on every call so a
    running process respects the deployment's current configuration. Constructing the
    backend does not prove the daemon or images are usable — that is what
    :func:`sandbox_preflight` is for, and a missing image still fails closed at run time.
    """
    if configured_backend() != BACKEND_DOCKER:
        return None
    global _backend
    if _backend is None:
        with _lock:
            if _backend is None:
                _backend = DockerExecutionBackend()
    return _backend


def sandbox_preflight() -> dict[str, Any]:
    """Report whether the sandbox is safe to enable. Read-only; runs no learner code.

    Used by the enablement gate (SECURITY_S0B §14) and by the acceptance harness. A
    ``ready`` of False on ANY field means execution must stay disabled.
    """
    report: dict[str, Any] = {
        "backend_configured": configured_backend(),
        "docker_cli": None,
        "docker_daemon": False,
        "images": {},
        "missing_images": [],
        "ready": False,
    }
    if configured_backend() != BACKEND_DOCKER:
        report["reason"] = "backend_not_configured"
        return report

    backend = DockerExecutionBackend()
    report["docker_cli"] = shutil.which("docker")
    report["docker_daemon"] = backend.available()
    if not report["docker_daemon"]:
        report["reason"] = "docker_daemon_unavailable"
        return report

    missing = backend.missing_images()
    report["images"] = dict(IMAGES)
    report["missing_images"] = missing
    report["ready"] = not missing
    if missing:
        report["reason"] = "images_missing"
    return report
