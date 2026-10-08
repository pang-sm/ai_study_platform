"""SECURITY_S0B Stage 5A — runner IPC protocol acceptance, run as the WEB identity.

Executed as `zhixue-web` from the application tree with the runner listening on a TEST
socket. It exercises the real client (`core.sandbox.runner_client`) and the raw wire, so a
pass means the web identity can use the runner exactly as the application would — and that
everything it is not allowed to send is refused.

Run with SANDBOX_RUNNER_SOCKET pointing at the test socket.
"""
from __future__ import annotations

import json
import os
import sys

import httpx

sys.path.insert(0, "/opt/ai_study_platform/backend")

from core.sandbox.runner_client import SandboxRunnerClient  # noqa: E402
from core.sandbox.types import ExecutionRequest, SourceFile, Verdict  # noqa: E402

SOCK = os.environ["SANDBOX_RUNNER_SOCKET"]
PASS: list[str] = []
FAIL: list[str] = []


def check(name: str, condition: bool, detail: object = "") -> None:
    (PASS if condition else FAIL).append(name)
    suffix = "" if condition else f"  — {detail!r}"
    print(f"  {'PASS' if condition else 'FAIL'}  {name}{suffix}")


def raw(method: str, path: str, body: bytes | None = None, headers: dict | None = None):
    transport = httpx.HTTPTransport(uds=SOCK)
    with httpx.Client(transport=transport, base_url="http://runner", timeout=90) as client:
        return client.request(method, path, content=body, headers=headers)


def post(payload: dict):
    return raw("POST", "/run", json.dumps(payload).encode(),
               {"content-type": "application/json"})


print("── liveness ──")
check("GET /health over the Unix socket", raw("GET", "/health").status_code == 200)
check("GET /preflight over the Unix socket", raw("GET", "/preflight").status_code == 200)

print("── the wire refuses everything outside the contract ──")
good = {"language": "Python",
        "files": [{"relative_path": "main.py", "content": "print(1)"}],
        "entry_file": "main.py"}
for field, value in (("privileged", True), ("docker_args", ["--privileged"]),
                     ("image", "alpine"), ("mounts", [["/", "/host"]]),
                     ("env", {"A": "B"}), ("command", "sh -c id")):
    payload = dict(good)
    payload[field] = value
    response = post(payload)
    check(f"extra field {field!r} rejected (422)", response.status_code == 422,
          response.status_code)
check("unknown language rejected (422)",
      post({"language": "Ruby", "files": [{"relative_path": "m.rb", "content": "puts 1"}],
            "entry_file": "m.rb"}).status_code == 422)
check("absolute path in files rejected (422)",
      post({"language": "Python",
            "files": [{"relative_path": "/etc/passwd", "content": "x"}],
            "entry_file": "/etc/passwd"}).status_code == 422)
check("traversal path in files rejected (422)",
      post({"language": "Python",
            "files": [{"relative_path": "../../etc/passwd", "content": "x"}],
            "entry_file": "../../etc/passwd"}).status_code == 422)
oversize = json.dumps({"language": "Python",
                       "files": [{"relative_path": "main.py", "content": "x" * (2 * 1024 * 1024)}],
                       "entry_file": "main.py"}).encode()
check("oversize body rejected (413)",
      raw("POST", "/run", oversize, {"content-type": "application/json"}).status_code == 413,
      raw("POST", "/run", oversize, {"content-type": "application/json"}).status_code)

print("── the real client works end to end (one bounded run) ──")
client = SandboxRunnerClient(socket_path=SOCK)
result = client.run(ExecutionRequest(
    language="Python", files=(SourceFile("main.py", "print('ipc-ok')"),), entry_file="main.py",
))
check("bounded run reaches ACCEPTED", result.verdict is Verdict.ACCEPTED,
      (result.verdict, result.internal_error))
check("stdout is exactly what the program wrote", result.stdout.strip() == "ipc-ok",
      result.stdout)

print("── fail-closed ──")
missing = SandboxRunnerClient(socket_path="/run/zhixue-sandbox-test/absent.sock")
absent_result = missing.run(ExecutionRequest(
    language="Python", files=(SourceFile("main.py", "print(1)"),), entry_file="main.py",
))
check("a missing socket yields INTERNAL_ERROR, never a host run",
      absent_result.verdict is Verdict.INTERNAL_ERROR, absent_result.verdict)

print(f"PROTOCOL PASS={len(PASS)} FAIL={len(FAIL)}")
sys.exit(1 if FAIL else 0)
