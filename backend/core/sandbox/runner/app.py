"""Sandbox runner service — SECURITY_S0B-P1.

A minimal FastAPI app bound to a Unix-domain socket, running as the least-privileged
`zhixue-sandbox` user next to a rootless Docker daemon. It is the ONLY component that
spawns learner containers, and it accepts only the bounded request shape.

    POST /run            one bounded compile+run  (or compile_only diagnosis)
    GET  /preflight      is the rootless daemon + pinned image pool ready
    WS   /run/interactive  a bounded interactive/streaming session for the terminals

Launch (systemd `zhixue-sandbox-runner`):

    uvicorn core.sandbox.runner.app:app --uds /run/zhixue-sandbox/runner.sock
"""
from __future__ import annotations

import asyncio
import json
import shutil
from typing import Any

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

from core.sandbox.docker_backend import DockerExecutionBackend, container_semaphore
from core.sandbox.limits import IMAGES, MAX_TOTAL_SOURCE_BYTES
from core.sandbox.runner.interactive import InteractiveSession
from core.sandbox.runner.schemas import ExecutionRequestModel, result_to_dict
from core.sandbox.types import ExecutionResult, Verdict

# The whole request body may never exceed the total source budget plus a small envelope.
MAX_REQUEST_BYTES = MAX_TOTAL_SOURCE_BYTES + 64 * 1024

app = FastAPI(title="zhixue-sandbox-runner", docs_url=None, redoc_url=None, openapi_url=None)
_backend = DockerExecutionBackend()


@app.middleware("http")
async def _limit_body(request: Request, call_next):
    length = request.headers.get("content-length")
    if length is not None:
        try:
            if int(length) > MAX_REQUEST_BYTES:
                return JSONResponse(status_code=413, content={"detail": "request too large"})
        except ValueError:
            return JSONResponse(status_code=400, content={"detail": "bad content-length"})
    return await call_next(request)


@app.get("/health")
def health() -> dict:
    """Liveness only — does not touch the daemon."""
    return {"status": "ok"}


@app.get("/preflight")
def preflight() -> dict:
    """Read-only readiness report. Runs no learner code."""
    report: dict[str, Any] = {
        "docker_cli": shutil.which("docker"),
        "docker_daemon": False,
        "images": dict(IMAGES),
        "missing_images": [],
        "ready": False,
    }
    report["docker_daemon"] = _backend.available()
    if not report["docker_daemon"]:
        report["reason"] = "docker_daemon_unavailable"
        return report
    missing = _backend.missing_images()
    report["missing_images"] = missing
    report["ready"] = not missing
    if missing:
        report["reason"] = "images_missing"
    return report


@app.post("/run")
def run(request: ExecutionRequestModel) -> dict:
    """One bounded compile+run (or a compile-only diagnosis). Carries no caller argv."""
    if not container_semaphore().acquire(timeout=20):
        return result_to_dict(ExecutionResult(
            language=request.language, verdict=Verdict.INTERNAL_ERROR,
            internal_error="sandbox_concurrency_limit",
        ))
    try:
        return result_to_dict(_backend.run(request.to_request()))
    finally:
        container_semaphore().release()


@app.websocket("/run/interactive")
async def run_interactive(ws: WebSocket) -> None:
    """A bounded interactive/streaming session. Everything is server-fixed but the source."""
    await ws.accept()
    session: InteractiveSession | None = None
    acquired = False
    try:
        start = json.loads(await ws.receive_text())
        request = ExecutionRequestModel.model_validate(start.get("request") or {})
        pty = bool(start.get("pty", True))
    except Exception:
        await ws.send_text(json.dumps({"type": "error", "message": "invalid start frame"}))
        await ws.close(code=1008)
        return

    if not container_semaphore().acquire(timeout=20):
        await ws.send_text(json.dumps({"type": "error", "message": "sandbox_concurrency_limit"}))
        await ws.close(code=1013)
        return
    acquired = True

    try:
        session = InteractiveSession(request.to_request(), pty=pty)
        frames = await asyncio.to_thread(session.prepare)
        for frame in frames:
            await ws.send_text(json.dumps(frame, ensure_ascii=False))
        if session.compile_failed:
            await ws.send_text(json.dumps(
                {"type": "exit", "exit_code": 1, "timed_out": False, "stdout": "",
                 "stderr": "", "compile_failed": True},
                ensure_ascii=False))
            return
        await asyncio.to_thread(session.start)
        await ws.send_text(json.dumps({"type": "status", "message": "程序正在运行"}, ensure_ascii=False))

        while True:
            out = session.drain()
            exiting = any(f.get("type") == "__exit__" for f in out)
            for frame in out:
                if frame.get("type") == "__exit__":
                    continue
                await ws.send_text(json.dumps(frame, ensure_ascii=False))
            if exiting:
                await ws.send_text(json.dumps(session.exit_frame(), ensure_ascii=False))
                return
            try:
                raw = await asyncio.wait_for(ws.receive_text(), timeout=0.1)
            except asyncio.TimeoutError:
                continue
            except WebSocketDisconnect:
                return
            try:
                message = json.loads(raw)
            except ValueError:
                continue
            kind = message.get("type")
            if kind == "stdin":
                session.send_stdin(str(message.get("data") or ""))
            elif kind == "eof":
                session.send_eof()
            elif kind in ("interrupt", "stop"):
                session.interrupt()
    except Exception as exc:  # never leak internals to the caller
        try:
            await ws.send_text(json.dumps({"type": "error", "message": type(exc).__name__}))
        except Exception:
            pass
    finally:
        if session is not None:
            await asyncio.to_thread(session.cleanup)
        if acquired:
            container_semaphore().release()
        try:
            await ws.close()
        except Exception:
            pass
