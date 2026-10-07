"""The ONE client for the sandbox runner service — SECURITY_S0B-P1.

The web process holds NO Docker access. This module is the only way learner code is
executed from the web side, and it reaches a least-privileged runner over a Unix-domain
socket. It imports no ``docker`` / ``shutil`` / ``subprocess`` and has **no host or rootful
fallback**: every transport / timeout / shape failure collapses to a fail-closed
``INTERNAL_ERROR`` (never a hang, never a 500, never a host spawn).
"""
from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager

import httpx

from core.config import sandbox_runner_socket, sandbox_runner_timeout
from core.sandbox.types import (
    CompileResult,
    ExecutionRequest,
    ExecutionResult,
    Verdict,
)

logger = logging.getLogger("sandbox.runner")

# Upper bound on a runner response we are willing to read.
MAX_RESPONSE_BYTES = 2_000_000


class SandboxRunnerUnavailable(Exception):
    """The runner could not be reached, timed out, or answered nonsense."""


def _body(request: ExecutionRequest) -> dict:
    """Project an ExecutionRequest onto the runner wire shape."""
    return {
        "language": request.language,
        "files": [
            {"relative_path": f.relative_path, "content": f.content} for f in request.files
        ],
        "entry_file": request.entry_file,
        "main_class": request.main_class,
        "stdin": request.stdin,
        "compile_files": (
            list(request.compile_files) if request.compile_files is not None else None
        ),
        "wall_time_ms": request.wall_time_ms,
        "compile_only": request.compile_only,
    }


def _verdict(raw: object) -> Verdict:
    try:
        return Verdict(str(raw))
    except ValueError:
        return Verdict.INTERNAL_ERROR


def _result_from_payload(payload: dict, language: str) -> ExecutionResult:
    compile_block = payload.get("compile")
    compile_result = None
    if isinstance(compile_block, dict):
        compile_result = CompileResult(
            ok=bool(compile_block.get("ok")),
            diagnostic=str(compile_block.get("diagnostic") or ""),
        )
    exit_code = payload.get("exit_code")
    return ExecutionResult(
        language=str(payload.get("language") or language),
        verdict=_verdict(payload.get("verdict")),
        stdout=str(payload.get("stdout") or ""),
        stderr=str(payload.get("stderr") or ""),
        exit_code=exit_code if isinstance(exit_code, int) else None,
        duration_ms=int(payload.get("duration_ms") or 0),
        timed_out=bool(payload.get("timed_out")),
        output_truncated=bool(payload.get("output_truncated")),
        compile=compile_result,
        internal_error=str(payload.get("internal_error") or ""),
    )


class SandboxRunnerClient:
    """Bounded, fail-closed access to the sandbox runner over a Unix-domain socket."""

    def __init__(self, *, socket_path: str | None = None, timeout: float | None = None,
                 transport: httpx.BaseTransport | None = None):
        self._socket = socket_path or sandbox_runner_socket()
        self._timeout = float(timeout if timeout is not None else sandbox_runner_timeout())
        # ``transport`` is the seam a test stands in below the HTTP boundary; never set in prod.
        self._transport = transport

    @property
    def socket_path(self) -> str:
        return self._socket

    def _transport_for(self) -> httpx.BaseTransport:
        return self._transport or httpx.HTTPTransport(uds=self._socket)

    def _fail(self, language: str, reason: str) -> ExecutionResult:
        return ExecutionResult(
            language=language, verdict=Verdict.INTERNAL_ERROR, internal_error=reason
        )

    def run(self, request: ExecutionRequest) -> ExecutionResult:
        """One bounded compile+run. Never raises — a failure is an INTERNAL_ERROR result."""
        try:
            with httpx.Client(base_url="http://sandbox-runner", timeout=self._timeout,
                              transport=self._transport_for()) as client:
                response = client.post("/run", json=_body(request))
        except Exception as exc:  # noqa: BLE001 — ANY transport failure must fail closed
            return self._fail(request.language, type(exc).__name__)
        if response.status_code != 200:
            return self._fail(request.language, f"http_{response.status_code}")
        if len(response.content) > MAX_RESPONSE_BYTES:
            return self._fail(request.language, "response_too_large")
        try:
            payload = response.json()
        except ValueError:
            return self._fail(request.language, "non_json_response")
        if not isinstance(payload, dict):
            return self._fail(request.language, "unexpected_body")
        return _result_from_payload(payload, request.language)

    def preflight(self) -> dict:
        """Read-only readiness probe. Never raises; returns ``ready: False`` on any failure."""
        try:
            with httpx.Client(base_url="http://sandbox-runner", timeout=5.0,
                              transport=self._transport_for()) as client:
                response = client.get("/preflight")
        except Exception as exc:  # noqa: BLE001 — any failure means "not ready"
            return {"ready": False, "reason": type(exc).__name__}
        if response.status_code != 200:
            return {"ready": False, "reason": f"http_{response.status_code}"}
        try:
            payload = response.json()
        except ValueError:
            return {"ready": False, "reason": "non_json_response"}
        if not isinstance(payload, dict):
            return {"ready": False, "reason": "unexpected_body"}
        return payload

    @asynccontextmanager
    async def open_interactive(self, request: ExecutionRequest, *, pty: bool = True):
        """Open a bounded interactive session over the UDS. Raises SandboxRunnerUnavailable."""
        from websockets.asyncio.client import unix_connect

        start = {"type": "start", "pty": pty, "request": _body(request)}
        try:
            ws = await unix_connect(path=self._socket, uri="ws://localhost/run/interactive")
        except Exception as exc:
            raise SandboxRunnerUnavailable(type(exc).__name__) from exc
        try:
            await ws.send(json.dumps(start))
            yield ws
        finally:
            try:
                await ws.close()
            except Exception:
                pass


_default_client: SandboxRunnerClient | None = None


def get_runner_client() -> SandboxRunnerClient:
    """The process-wide client. Configuration is read once per process."""
    global _default_client
    if _default_client is None:
        _default_client = SandboxRunnerClient()
    return _default_client


def reset_runner_client() -> None:
    """Drop the cached client (used when configuration changes, and by tests)."""
    global _default_client
    _default_client = None
