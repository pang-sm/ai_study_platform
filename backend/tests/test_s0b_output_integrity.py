"""SECURITY_S0B-P1 — byte-exact output capture and a stable over-limit verdict.

The container's stdout/stderr are captured through two host-mounted FILES, never the
container CLI's attached-output relay (rootless Podman 3.4.4 truncates that). These tests
pin the contract at the exact boundaries, per stream:

* under the cap  -> ACCEPTED, byte count and SHA-256 exactly match what the program wrote;
* over  the cap -> a stable OUTPUT_LIMIT, never ACCEPTED, never silently truncated.

Skipped unless a container runtime with the pinned images is available. Run on a POSIX host
with Podman (rootless) or Docker.
"""
from __future__ import annotations

import glob
import hashlib
import os
import shutil
import subprocess
import tempfile

import pytest

from core.sandbox import docker_backend as db
from core.sandbox.limits import IMAGES, OUTPUT_CAP_BYTES
from core.sandbox.types import ExecutionRequest, SourceFile, Verdict


def _runtime() -> str | None:
    if os.name != "posix":
        return None
    for name in ("podman", "docker"):
        if shutil.which(name) is None:
            continue
        backend = db.DockerExecutionBackend(runtime=name)
        try:
            if backend.available():
                return name
        except Exception:  # noqa: BLE001
            continue
    return None


_RUNTIME = _runtime()
pytestmark = pytest.mark.skipif(_RUNTIME is None, reason="no usable container runtime")

_backend = db.DockerExecutionBackend(runtime=_RUNTIME or "docker")

ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
CAP = OUTPUT_CAP_BYTES
UNDER = [0, 256 * 1024, 768 * 1024, CAP - 1]
OVER = [CAP + 1, 2 * CAP]


def _pattern(n: int) -> bytes:
    return ((ALPHABET * (n // len(ALPHABET) + 1))[:n]).encode()


def _program(n: int, stream: str) -> str:
    buf = "sys.stdout.buffer" if stream == "stdout" else "sys.stderr.buffer"
    return (
        "import sys\n"
        f"n = {n}\n"
        f"data = ('{ALPHABET}' * (n // {len(ALPHABET)} + 1))[:n]\n"
        f"{buf}.write(data.encode())\n"
    )


def _run(body: str):
    return _backend.run(ExecutionRequest(
        language="Python", files=(SourceFile("main.py", body),), entry_file="main.py",
    ))


@pytest.mark.parametrize("stream", ["stdout", "stderr"])
@pytest.mark.parametrize("n", UNDER, ids=[f"under-{n}" for n in UNDER])
def test_under_cap_is_byte_exact(stream, n):
    result = _run(_program(n, stream))
    captured = result.stdout if stream == "stdout" else result.stderr
    other = result.stderr if stream == "stdout" else result.stdout
    assert result.verdict is Verdict.ACCEPTED, (result.verdict, result.internal_error)
    encoded = captured.encode()
    assert len(encoded) == n
    assert hashlib.sha256(encoded).hexdigest() == hashlib.sha256(_pattern(n)).hexdigest()
    assert other == ""


@pytest.mark.parametrize("stream", ["stdout", "stderr"])
@pytest.mark.parametrize("n", OVER, ids=[f"over-{n}" for n in OVER])
def test_over_cap_is_a_stable_output_limit(stream, n):
    result = _run(_program(n, stream))
    assert result.verdict is Verdict.OUTPUT_LIMIT, (result.verdict, result.internal_error)
    assert result.verdict is not Verdict.ACCEPTED
    assert result.output_truncated is True
    captured = result.stdout if stream == "stdout" else result.stderr
    assert len(captured.encode()) <= CAP


def test_both_streams_under_the_cap_stay_separate_and_exact():
    body = _program(768 * 1024, "stdout") + _program(768 * 1024, "stderr")
    result = _run(body)
    assert result.verdict is Verdict.ACCEPTED
    assert result.stdout.encode() == _pattern(768 * 1024)
    assert result.stderr.encode() == _pattern(768 * 1024)


def test_both_streams_over_the_cap_is_output_limit():
    body = _program(2 * CAP, "stdout") + _program(2 * CAP, "stderr")
    result = _run(body)
    assert result.verdict is Verdict.OUTPUT_LIMIT
    assert result.verdict is not Verdict.ACCEPTED


def test_a_program_creating_many_files_cannot_grow_the_host_disk():
    """Only the two output files may reach the host: extra files land in the container tmpfs."""
    body = (
        "for i in range(5000):\n"
        "    try:\n"
        "        open(f'/tmp/zhixue_junk_{i}', 'wb').write(b'x' * 4096)\n"
        "    except OSError:\n"
        "        break\n"
        "print('done')\n"
    )
    before = set(glob.glob(os.path.join(tempfile.gettempdir(), "zhixue_sandbox_*")))
    result = _run(body)
    after = set(glob.glob(os.path.join(tempfile.gettempdir(), "zhixue_sandbox_*")))
    assert result.verdict in {Verdict.ACCEPTED, Verdict.OUTPUT_LIMIT}
    assert after - before == set(), f"run dirs leaked: {after - before}"
    leftovers = subprocess.run(
        [_RUNTIME, "ps", "-a", "--filter", "name=zhixue-sbx-", "--format", "{{.Names}}"],
        capture_output=True, text=True, timeout=30,
    )
    assert leftovers.stdout.strip() == "", f"containers leaked: {leftovers.stdout}"
