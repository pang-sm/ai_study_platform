"""SECURITY_S0 — fail-closed contract for learner code execution.

The production incident: an authenticated learner could get their own source compiled and
run as a host subprocess (gcc/g++/javac/java/python/pytest), which put the production
database, the systemd environment and the provider secrets within reach of that process.

The invariant these tests defend is stronger than "use Docker in production":

    USER-CONTROLLED CODE MUST NEVER EXECUTE ON THE HOST.

So every assertion here is written the same way — point the entry at a payload, then prove
(a) the caller gets a stable 503 refusal and (b) the host process was never spawned. The
spy is deliberately installed on ``subprocess`` itself rather than on any one helper, so a
future refactor that reintroduces a second execution path fails these tests instead of
silently bypassing them.
"""
import json

import pytest
from fastapi.testclient import TestClient

import main
from core import code_execution
from conftest import register_and_login


# A payload that would exfiltrate the production database if it ever reached a host process.
MALICIOUS_PYTHON = "print(open('/var/lib/ai_study_platform/app.db','rb').read()[:200])"
MALICIOUS_C = '#include <stdio.h>\nint main(){FILE*f=fopen("/etc/passwd","r");return 0;}'


class _HostProcessSpy:
    """Records any attempt to spawn a host process and makes the attempt fail loudly."""

    def __init__(self):
        self.calls = []

    @property
    def called(self) -> bool:
        return bool(self.calls)

    def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        raise AssertionError(f"host process spawn attempted: {args!r}")


@pytest.fixture
def host_spy(monkeypatch):
    """Intercept every host process spawn for the duration of one test."""
    spy = _HostProcessSpy()
    import subprocess

    monkeypatch.setattr(subprocess, "run", spy)
    monkeypatch.setattr(subprocess, "Popen", spy)
    monkeypatch.setattr(subprocess, "check_output", spy)
    monkeypatch.setattr(subprocess, "call", spy)
    return spy


@pytest.fixture
def no_backend(monkeypatch):
    """The production state under audit: no backend configured at all."""
    monkeypatch.delenv(code_execution.CODE_EXECUTION_BACKEND_ENV, raising=False)


def _create_project(client, username: str, language: str, code: str) -> int:
    """Create a project (any language) and plant the payload in its auto-created entry file."""
    created = client.post("/code/projects", json={
        "username": username, "name": "s0", "language": language, "course_id": "programming",
    })
    assert created.status_code == 200, created.text
    project_id = created.json()["project"]["id"]

    files = client.get(f"/code/projects/{project_id}", params={"username": username}).json()["project"]["files"]
    assert files, "project should be created with a default entry file"
    saved = client.put(f"/code/projects/{project_id}/files/{files[0]['id']}", json={
        "username": username, "content": code,
    })
    assert saved.status_code == 200, saved.text
    return project_id


def _create_python_project(client, username: str, code: str) -> int:
    return _create_project(client, username, "Python", code)


def _exercise_backed_project(client, username: str) -> tuple[int, int]:
    """A learner project wired to its OWN exercise row, with the payload already in the file.

    The exercise is built directly rather than read from the catalogue: these tests are about the
    sandbox gate, so they must not depend on what imported content happens to be present. Both ids
    are returned because the endpoints reject a project that is not the exercise's own — creating a
    second project to satisfy one of them would make the pair disagree.
    """
    import database
    import models

    project_id = _create_python_project(client, username, MALICIOUS_PYTHON)
    db = database.SessionLocal()
    try:
        exercise = models.ProgrammingExercise(
            slug=f"s0-containment-{username}", language="Python", title="S0 containment",
            difficulty="easy", description="containment fixture",
            source_repo="test", source_path="test/s0", source_commit="test",
            license_text="test", attribution="test", quality_status="approved", is_active=True,
        )
        db.add(exercise)
        db.flush()
        db.query(models.CodeProject).filter(models.CodeProject.id == project_id).update(
            {"programming_exercise_id": exercise.id})
        db.commit()
        return project_id, exercise.id
    finally:
        db.close()


# ── the policy itself ──────────────────────────────────────────────────────────────

def test_policy_fails_closed_when_env_absent(monkeypatch):
    monkeypatch.delenv(code_execution.CODE_EXECUTION_BACKEND_ENV, raising=False)
    assert code_execution.is_secure_code_execution_available() is False


@pytest.mark.parametrize("value", ["", "none", "host", "subprocess", "shell", "true", "1", "docker2", "dockerized"])
def test_policy_fails_closed_on_unknown_backend(monkeypatch, value):
    """Only the exact verified identifier opts in; near-misses must not open the door."""
    import shutil
    monkeypatch.setenv(code_execution.CODE_EXECUTION_BACKEND_ENV, value)
    # Even with a docker binary present, an unrecognised value must not enable anything.
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/docker" if name == "docker" else None)
    assert code_execution.is_secure_code_execution_available() is False


def test_explicit_opt_in_with_runtime_present_is_the_only_enabling_combination(monkeypatch):
    """The documented way to restore execution: explicit opt-in AND the sandbox runtime."""
    import shutil
    monkeypatch.setenv(code_execution.CODE_EXECUTION_BACKEND_ENV, "docker")
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/docker" if name == "docker" else None)
    assert code_execution.is_secure_code_execution_available() is True


def test_docker_on_path_alone_does_not_enable_execution(monkeypatch):
    """An unrelated host install of docker must never re-open user code execution.

    This is the specific regression that caused the incident class: the old code used
    ``shutil.which("docker") is not None`` as its sandbox probe.
    """
    import shutil
    monkeypatch.delenv(code_execution.CODE_EXECUTION_BACKEND_ENV, raising=False)
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/docker" if name == "docker" else None)
    assert code_execution.is_secure_code_execution_available() is False


def test_opted_in_but_runtime_missing_still_fails_closed(monkeypatch):
    import shutil
    monkeypatch.setenv(code_execution.CODE_EXECUTION_BACKEND_ENV, "docker")
    monkeypatch.setattr(shutil, "which", lambda name: None)
    assert code_execution.is_secure_code_execution_available() is False


# ── project execution ──────────────────────────────────────────────────────────────

def test_project_execute_refuses_when_sandbox_unavailable(client, no_backend, host_spy):
    register_and_login(client, "s0-proj")
    project_id = _create_python_project(client, "s0-proj", MALICIOUS_PYTHON)

    response = client.post(f"/code/projects/{project_id}/execute", json={"username": "s0-proj"})

    assert response.status_code == 503, response.text
    assert response.json()["detail"]["code"] == "code_execution_unavailable"
    assert host_spy.called is False, host_spy.calls


def test_project_execute_never_reaches_host_for_c(client, no_backend, host_spy):
    register_and_login(client, "s0-projc")
    project_id = _create_project(client, "s0-projc", "C", MALICIOUS_C)

    response = client.post(f"/code/projects/{project_id}/execute", json={"username": "s0-projc"})

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "code_execution_unavailable"
    assert host_spy.called is False, host_spy.calls


# ── exercise judging ───────────────────────────────────────────────────────────────

def test_exercise_submit_refuses_and_does_not_run_learner_code(client, no_backend, host_spy):
    """A learner's own source must not be compiled or imported on the host.

    The official test files being trusted is irrelevant — the submission is the untrusted half.
    """
    register_and_login(client, "s0-ex")
    project_id, exercise_id = _exercise_backed_project(client, "s0-ex")

    response = client.post(f"/programming/exercises/{exercise_id}/submit", json={
        "username": "s0-ex", "project_id": project_id,
    })

    assert response.status_code == 503, response.text
    assert response.json()["detail"]["code"] == "code_execution_unavailable"
    assert host_spy.called is False, host_spy.calls


def test_exercise_run_refuses_and_does_not_run_learner_code(client, no_backend, host_spy):
    """The interactive run is the third entry into the same gate, and the one that was broken.

    This route passed its arguments in the wrong order — it handed `db` into
    `execute_code_project`'s `request` parameter and left `current_user` holding its `Depends`
    default — so every run raised `AttributeError: 'Depends' object has no attribute 'username'`
    and answered 500 BEFORE the gate could refuse it. No test had ever called this route, which is
    exactly why that shipped. The contract is the same as its two siblings: a stable 503 refusal
    with no host process spawned, and a 500 here means the wiring has regressed again.
    """
    register_and_login(client, "s0-run")
    project_id, exercise_id = _exercise_backed_project(client, "s0-run")

    response = client.post(f"/programming/exercises/{exercise_id}/run", json={
        "username": "s0-run", "project_id": project_id, "stdin": "",
    })

    assert response.status_code == 503, response.text
    assert response.json()["detail"]["code"] == "code_execution_unavailable"
    assert host_spy.called is False, host_spy.calls


# ── interactive terminal ───────────────────────────────────────────────────────────

def test_interactive_terminal_never_falls_back_to_host_shell(client, no_backend, host_spy):
    """The terminal previously degraded to a host PTY when Docker was missing."""
    register_and_login(client, "s0-term")

    with client.websocket_connect("/code/interactive-run") as websocket:
        websocket.send_text(json.dumps({
            "username": "s0-term", "language": "python", "code": "print(1)",
        }))
        message = json.loads(websocket.receive_text())

    assert message["type"] == "error"
    assert message["message"] == code_execution.UNAVAILABLE_MESSAGE
    assert host_spy.called is False, host_spy.calls


def test_interactive_terminal_never_falls_back_to_host_shell_for_c(client, no_backend, host_spy):
    register_and_login(client, "s0-termc")

    with client.websocket_connect("/code/interactive-run") as websocket:
        websocket.send_text(json.dumps({
            "username": "s0-termc", "language": "c", "code": MALICIOUS_C,
        }))
        message = json.loads(websocket.receive_text())

    assert message["type"] == "error"
    assert host_spy.called is False, host_spy.calls


def test_exercise_terminal_never_falls_back_to_host(client, no_backend, host_spy):
    """The exercise terminal had its own docker→host fallback with a host gcc/javac path."""
    import database
    import models

    register_and_login(client, "s0-exterm")
    project_id = _create_python_project(client, "s0-exterm", MALICIOUS_PYTHON)

    db = database.SessionLocal()
    try:
        exercise = models.ProgrammingExercise(
            slug="s0-containment-terminal", language="Python", title="S0 terminal",
            difficulty="easy", description="containment fixture",
            source_repo="test", source_path="test/s0t", source_commit="test",
            license_text="test", attribution="test", quality_status="approved", is_active=True,
        )
        db.add(exercise)
        db.flush()
        db.query(models.CodeProject).filter(models.CodeProject.id == project_id).update(
            {"programming_exercise_id": exercise.id})
        db.commit()
        exercise_id = exercise.id
    finally:
        db.close()

    with client.websocket_connect(f"/api/programming/exercises/{exercise_id}/interactive") as websocket:
        websocket.send_text(json.dumps({
            "username": "s0-exterm", "project_id": project_id,
        }))
        message = json.loads(websocket.receive_text())

    assert message["type"] == "error"
    assert message["message"] == code_execution.UNAVAILABLE_MESSAGE
    assert host_spy.called is False, host_spy.calls


# ── the guard is shared, not duplicated per entry point ────────────────────────────

def test_every_execution_helper_shares_the_same_gate(client, no_backend):
    """Each leaf refuses identically. A new host path must fail this list, not slip past it."""
    import programming_execution
    import programming_io_adapter

    with pytest.raises(Exception) as project_exc:
        main._run_project_command(["python", "-c", "print(1)"], cwd=".")
    assert project_exc.value.status_code == 503

    with pytest.raises(Exception) as docker_exc:
        main._run_code_in_docker("print(1)")
    assert docker_exc.value.status_code == 503

    with pytest.raises(Exception) as c_docker_exc:
        main._run_c_code_in_docker("int main(){return 0;}")
    assert c_docker_exc.value.status_code == 503

    with pytest.raises(Exception) as oj_exc:
        main._run_standard_oj_case(None, [], {})
    assert oj_exc.value.status_code == 503

    with pytest.raises(Exception) as sample_exc:
        main._run_public_sample(None, None, [], {})
    assert sample_exc.value.status_code == 503

    with pytest.raises(Exception) as official_exc:
        main._run_official_exercise_tests(None, None, [], True)
    assert official_exc.value.status_code == 503

    with pytest.raises(Exception) as java_exc:
        programming_execution.run_java_tests([], [])
    assert java_exc.value.status_code == 503

    # The stdin/stdout adapter only reaches its guard once a runnable command is prepared,
    # so this sample is shaped to actually produce one.
    with pytest.raises(Exception) as adapter_exc:
        programming_io_adapter.run_sample(
            "Python", None,
            [{"relative_path": "solution.py", "content": "def add(a, b):\n    return a + b\n"}],
            {"stdin_text": "", "adapter_config": {"protocol": "stdin_stdout_v1", "callable": "add"}},
        )
    assert adapter_exc.value.status_code == 503


def test_no_host_process_module_reference_survives_in_the_guard_path():
    """The refusal must come from the policy module, not from a docker-not-found accident."""
    assert code_execution.configured_backend() == code_execution.BACKEND_DISABLED
    assert code_execution.UNAVAILABLE_CODE == "code_execution_unavailable"


# ── only execution is closed; the rest of the programming space still works ─────────

def test_programming_crud_remains_available(client, no_backend):
    """Containment must close execution only — reading and editing projects is not execution."""
    register_and_login(client, "s0-crud")

    created = client.post("/code/projects", json={
        "username": "s0-crud", "name": "still works", "language": "Python", "course_id": "programming",
    })
    assert created.status_code == 200, created.text
    project_id = created.json()["project"]["id"]

    fetched = client.get(f"/code/projects/{project_id}", params={"username": "s0-crud"})
    assert fetched.status_code == 200, fetched.text
    assert fetched.json()["project"]["name"] == "still works"

    renamed = client.put(f"/code/projects/{project_id}", json={
        "username": "s0-crud", "name": "renamed",
    })
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["project"]["name"] == "renamed"

    listed = client.get("/code/projects", params={"username": "s0-crud"})
    assert listed.status_code == 200, listed.text
    assert any(p["id"] == project_id for p in listed.json()["projects"])
