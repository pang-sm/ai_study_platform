"""SECURITY_S0B — end-to-end judging through the HTTP API with the sandbox enabled.

Proves the learner-facing contract still holds when execution actually happens:
``/run`` returns the program's output, ``/submit`` judges public + hidden cases, a
compile error is reported as such, and — the security-critical part — hidden case
input and expected output never appear in the submission response.

Skipped without Docker (like the isolation suite).
"""
from __future__ import annotations

import json
import os

import pytest
from fastapi.testclient import TestClient  # noqa: F401  (imported for the type in fixtures)

from conftest import register_and_login
from core.sandbox.docker_backend import DockerExecutionBackend
from core.sandbox.limits import IMAGES

_backend = DockerExecutionBackend()


def _probe() -> tuple[bool, set[str]]:
    try:
        if not _backend.available():
            return False, set()
        return True, set(_backend.missing_images())
    except Exception:  # noqa: BLE001
        return False, set()


_DAEMON, _MISSING = _probe()
pytestmark = [
    pytest.mark.skipif(not _DAEMON, reason="docker daemon unavailable"),
    pytest.mark.skipif(os.name != "posix", reason="the runner UDS requires POSIX"),
]

# Every test below runs Python except the parametrized one; C is used by one case.
PYTHON = pytest.mark.skipif(IMAGES["Python"] in _MISSING, reason="python image not present")


def _lang_params():
    return [pytest.param(l, marks=pytest.mark.skipif(IMAGES[l] in _MISSING, reason=f"{IMAGES[l]} missing"))
            for l in ("Python", "C", "C++", "Java")]


ENTRY = {"Python": "main.py", "C": "main.c", "C++": "main.cpp", "Java": "Main.java"}

# Task: read one integer and print double it.
REFERENCE = {
    "Python": "import sys\nprint(int(sys.stdin.read().strip()) * 2)\n",
    "C": '#include <stdio.h>\nint main(void){long n;if(scanf("%ld",&n)!=1)return 1;printf("%ld\\n",n*2);return 0;}\n',
    "C++": '#include <iostream>\nint main(){long n;std::cin>>n;std::cout<<(n*2)<<"\\n";return 0;}\n',
    "Java": 'import java.util.*;\npublic class Main{public static void main(String[] a){Scanner s=new Scanner(System.in);System.out.println(s.nextLong()*2);}}\n',
}
WRONG = {
    "Python": "print(0)\n",
    "C": 'int main(void){printf("0\\n");return 0;}\n',
    "C++": '#include <iostream>\nint main(){std::cout<<"0"<<"\\n";return 0;}\n',
    "Java": 'public class Main{public static void main(String[] a){System.out.println(0);}}\n',
}

PUBLIC = json.dumps([{"samples": [
    {"id": "public-1", "name": "样例 1", "stdin_text": "2\n", "expected_stdout": "4\n"},
    {"id": "public-2", "name": "样例 2", "stdin_text": "5\n", "expected_stdout": "10\n"},
]}], ensure_ascii=False)
HIDDEN = json.dumps([{"samples": [
    {"id": "hidden-1", "name": "隐藏 1", "stdin_text": "87654321\n", "expected_stdout": "175308642\n"},
    {"id": "hidden-secret-marker", "name": "隐藏 2", "stdin_text": "31415926\n", "expected_stdout": "62831852\n"},
]}], ensure_ascii=False)


def _start_runner(sock_path: str):
    """Start the sandbox runner ASGI app on a temp Unix socket in a background thread."""
    import os
    import threading
    import time

    import uvicorn

    from core.sandbox.runner.app import app as runner_app

    config = uvicorn.Config(runner_app, uds=sock_path, log_level="warning", lifespan="off")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(200):
        if os.path.exists(sock_path):
            break
        time.sleep(0.05)
    return server, thread


@pytest.fixture
def sandbox_on(tmp_path, monkeypatch):
    """Enable the sandbox AND run a real runner over a temp Unix socket."""
    monkeypatch.setenv("CODE_EXECUTION_BACKEND", "docker")
    sock_path = str(tmp_path / "runner.sock")
    monkeypatch.setenv("SANDBOX_RUNNER_SOCKET", sock_path)
    from core import sandbox as _sandbox
    monkeypatch.setattr(_sandbox, "_client", None, raising=False)
    server, thread = _start_runner(sock_path)
    try:
        yield
    finally:
        server.should_exit = True
        thread.join(timeout=5)


def _make_exercise_project(client, username: str, language: str, code: str):
    created = client.post("/code/projects", json={
        "username": username, "name": "s0b", "language": language, "course_id": "programming",
    })
    assert created.status_code == 200, created.text
    project_id = created.json()["project"]["id"]
    files = client.get(f"/code/projects/{project_id}", params={"username": username}).json()["project"]["files"]
    entry = next(f for f in files if f["relative_path"] == ENTRY[language])
    saved = client.put(f"/code/projects/{project_id}/files/{entry['id']}", json={"username": username, "content": code})
    assert saved.status_code == 200, saved.text

    import database
    import models
    db = database.SessionLocal()
    try:
        exercise = models.ProgrammingExercise(
            slug=f"s0b-{username}-{language}", language=language, title="S0B judge",
            difficulty="easy", description="judge fixture",
            starter_files_json=json.dumps([{"path": ENTRY[language], "content": ""}]),
            public_tests_json=PUBLIC, hidden_tests_json=HIDDEN, official_test_files_json="[]",
            audit_report_json=json.dumps({"runner": "standard_io"}),
            source_repo="test", source_path="test/s0b", source_commit="test",
            license_text="test", attribution="test", quality_status="approved", is_active=True,
        )
        db.add(exercise)
        db.flush()
        db.query(models.CodeProject).filter(models.CodeProject.id == project_id).update(
            {"programming_exercise_id": exercise.id, "main_class": "Main"})
        db.commit()
        return project_id, exercise.id
    finally:
        db.close()


@pytest.mark.parametrize("language", _lang_params())
def test_submit_accepts_a_correct_solution(client, sandbox_on, language):
    username = f"s0b-ok-{language}".lower().replace("+", "p")
    register_and_login(client, username)
    project_id, exercise_id = _make_exercise_project(client, username, language, REFERENCE[language])

    response = client.post(f"/programming/exercises/{exercise_id}/submit", json={
        "username": username, "project_id": project_id,
    })
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["passed"] is True, payload.get("technical_details")
    assert payload["passed_count"] == 4 and payload["total_count"] == 4


@PYTHON
def test_submit_rejects_a_wrong_solution(client, sandbox_on):
    register_and_login(client, "s0b-wrong")
    project_id, exercise_id = _make_exercise_project(client, "s0b-wrong", "Python", WRONG["Python"])
    payload = client.post(f"/programming/exercises/{exercise_id}/submit", json={
        "username": "s0b-wrong", "project_id": project_id,
    }).json()
    assert payload["passed"] is False
    assert payload["passed_count"] < payload["total_count"]


@pytest.mark.skipif(IMAGES['C'] in _MISSING, reason='gcc image not present')
def test_submit_reports_a_compile_error(client, sandbox_on):
    register_and_login(client, "s0b-broken")
    project_id, exercise_id = _make_exercise_project(client, "s0b-broken", "C", "int main(void){ return oops(); }\n")
    payload = client.post(f"/programming/exercises/{exercise_id}/submit", json={
        "username": "s0b-broken", "project_id": project_id,
    }).json()
    assert payload["passed"] is False
    assert "compile" in payload["failed_categories"]


@PYTHON
def test_submit_never_leaks_hidden_cases(client, sandbox_on):
    """The hidden sample id and expected output must not appear anywhere in the response."""
    register_and_login(client, "s0b-secret")
    project_id, exercise_id = _make_exercise_project(client, "s0b-secret", "Python", REFERENCE["Python"])
    body = client.post(f"/programming/exercises/{exercise_id}/submit", json={
        "username": "s0b-secret", "project_id": project_id,
    }).text
    assert "hidden-secret-marker" not in body
    for secret in ("175308642", "87654321", "62831852", "31415926"):
        assert secret not in body, f"hidden case value leaked: {secret}"


@PYTHON
def test_run_executes_the_learners_current_code(client, sandbox_on):
    register_and_login(client, "s0b-run")
    project_id, exercise_id = _make_exercise_project(client, "s0b-run", "Python", REFERENCE["Python"])
    payload = client.post(f"/programming/exercises/{exercise_id}/run", json={
        "username": "s0b-run", "project_id": project_id, "stdin": "7\n",
    }).json()
    assert payload["success"] is True
    assert payload["stdout"].strip() == "14"


@pytest.mark.skipif(IMAGES['C'] in _MISSING, reason='gcc image not present')
def test_public_tests_run_and_return_cases(client, sandbox_on):
    register_and_login(client, "s0b-test")
    project_id, exercise_id = _make_exercise_project(client, "s0b-test", "C", REFERENCE["C"])
    payload = client.post(f"/programming/exercises/{exercise_id}/test", json={
        "username": "s0b-test", "project_id": project_id, "public_case_ids": ["public-1", "public-2"],
    }).json()
    assert payload["passed"] is True
    assert payload["passed_count"] == 2 and payload["total_count"] == 2
    assert payload["tests_executed"] == "public_only"
