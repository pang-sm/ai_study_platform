"""SECURITY_S0B-P1 — the load-bearing invariant: the WEB process holds no Docker access.

After privilege separation, learner code is executed only by the least-privileged runner
service. If any module reachable from the web app could import the Docker backend or build a
``docker run`` argv, the separation would be a fiction — so this test fails the build.

The ONLY modules allowed to touch ``core.sandbox.docker_backend`` live under
``core/sandbox/runner/`` (the runner service itself).
"""
from __future__ import annotations

import re
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]

# Web-side modules: the FastAPI app and its programming leaves, plus all of ``core`` except
# the runner package and the Docker backend it owns.
WEB_FILES = [
    BACKEND / "main.py",
    BACKEND / "programming_execution.py",
    BACKEND / "programming_io_adapter.py",
]


def _web_core_files() -> list[Path]:
    files: list[Path] = []
    for path in (BACKEND / "core").rglob("*.py"):
        rel = path.relative_to(BACKEND).as_posix()
        if rel == "core/sandbox/docker_backend.py":
            continue
        if rel.startswith("core/sandbox/runner/"):
            continue
        files.append(path)
    return files


FORBIDDEN = [
    (re.compile(r"from\s+core\.sandbox\.docker_backend|import\s+core\.sandbox\.docker_backend"),
     "imports the Docker execution backend"),
    (re.compile(r"\bDockerExecutionBackend\b"), "references DockerExecutionBackend"),
    (re.compile(r"""shutil\.which\(\s*['"]docker['"]\s*\)"""), "probes for a docker binary"),
    (re.compile(r"""['"]docker['"]\s*,\s*['"]run['"]"""), "builds a docker run argv"),
]


def _scan(path: Path, text: str) -> list[str]:
    problems = []
    for pattern, why in FORBIDDEN:
        for match in pattern.finditer(text):
            line = text.count("\n", 0, match.start()) + 1
            problems.append(f"{path.relative_to(BACKEND).as_posix()}:{line}: {why}")
    return problems


def test_no_web_module_reaches_for_docker():
    problems: list[str] = []
    for path in WEB_FILES + _web_core_files():
        problems.extend(_scan(path, path.read_text(encoding="utf-8")))
    assert problems == [], "the web process must have ZERO direct docker access:\n" + "\n".join(problems)


def test_the_sandbox_package_exposes_the_client_not_the_docker_backend():
    """``core.sandbox`` is the web-facing surface; it must not import the Docker backend."""
    import core.sandbox as sandbox
    assert hasattr(sandbox, "SandboxRunnerClient")
    assert not hasattr(sandbox, "DockerExecutionBackend")
    source = (BACKEND / "core/sandbox/__init__.py").read_text(encoding="utf-8")
    assert "docker_backend" not in source
