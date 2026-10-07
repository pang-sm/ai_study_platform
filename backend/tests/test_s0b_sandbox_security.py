"""SECURITY_S0B — the isolation properties of the container sandbox.

These tests run REAL containers and are skipped when Docker or a pinned image is
unavailable, so the unit suite stays green on a machine without Docker. They belong
to the proof that learner code cannot reach the host filesystem, the host network,
the host environment, or other learners' runs.

They are deliberately written against ``DockerExecutionBackend`` directly rather than
through an HTTP route: the properties under test are properties of the sandbox, and a
route test would only add an unrelated seam.
"""
from __future__ import annotations

import glob
import os
import tempfile
import uuid
from pathlib import Path

import pytest

from core.sandbox import ExecutionRequest, SourceFile, Verdict
from core.sandbox.docker_backend import DockerExecutionBackend
from core.sandbox.limits import IMAGES

_backend = DockerExecutionBackend()


def _probe() -> tuple[bool, set[str]]:
    try:
        if not _backend.available():
            return False, set()
        return True, set(_backend.missing_images())
    except Exception:  # noqa: BLE001 - any probe failure means "not ready"
        return False, set()


_DAEMON, _MISSING = _probe()

pytestmark = pytest.mark.skipif(not _DAEMON, reason="docker daemon unavailable")


def needs(language: str):
    """Mark a test that requires one language's pinned image."""
    return pytest.mark.skipif(IMAGES[language] in _MISSING, reason=f"{IMAGES[language]} not present")


LANG_PARAMS = [pytest.param(language, marks=needs(language)) for language in ["Python", "C", "C++", "Java"]]
NATIVE_PARAMS = [pytest.param(language, marks=needs(language)) for language in ["C", "C++", "Java"]]
PYTHON = needs("Python")


ENTRY = {"Python": "main.py", "C": "main.c", "C++": "main.cpp", "Java": "Main.java"}


def _source(language: str, body: str) -> SourceFile:
    return SourceFile(ENTRY[language], body)


def run(language: str, body: str, stdin: str = "", **kw):
    return _backend.run(ExecutionRequest(
        language=language, files=(_source(language, body),),
        entry_file=ENTRY[language], main_class="Main" if language == "Java" else None,
        stdin=stdin, **kw,
    ))


HELLO = {
    "Python": "import sys\nprint('HELLO', sys.stdin.read().strip())\n",
    "C": '#include <stdio.h>\nint main(){char b[64]={0};if(fgets(b,64,stdin))printf("HELLO %s", b);return 0;}\n',
    "C++": '#include <iostream>\nint main(){std::string s;std::cin>>s;std::cout<<"HELLO "<<s<<"\\n";return 0;}\n',
    "Java": 'import java.util.Scanner;\npublic class Main{public static void main(String[] a){Scanner s=new Scanner(System.in);System.out.println("HELLO "+s.next());}}\n',
}

BROKEN = {
    "C": "int main(){ return oops(); }\n",
    "C++": "int main(){ return oops(); }\n",
    "Java": "public class Main{ public static void main(String[] a){ int x = ; } }\n",
}

RUNTIME_THROW = {
    "Python": "raise ValueError('boom')\n",
    "C": 'int main(){int*p=0;return *p;}\n',
    "C++": 'int main(){int*p=nullptr;return *p;}\n',
    "Java": 'public class Main{public static void main(String[] a){throw new RuntimeException("boom");}}\n',
}


# ── positive path ──────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("language", LANG_PARAMS)
def test_hello_world_runs_inside_the_sandbox(language):
    result = run(language, HELLO[language], stdin="world")
    assert result.verdict is Verdict.ACCEPTED, (language, result.stderr)
    assert "HELLO world" in result.stdout


@needs("Java")
def test_java_multifile_project_compiles_and_runs():
    """12 of the 240 catalogue exercises ship several .java files (entry Main.java)."""
    result = _backend.run(ExecutionRequest(
        language="Java",
        files=(
            SourceFile("Main.java", 'import java.util.*;\npublic class Main{public static void main(String[] a){'
                                    'Scanner s=new Scanner(System.in);System.out.println(Helper.twice(s.nextLong()));}}\n'),
            SourceFile("Helper.java", "public class Helper{ static long twice(long n){ return n*2; } }\n"),
        ),
        entry_file="Main.java", main_class="Main", stdin="21\n",
    ))
    assert result.verdict is Verdict.ACCEPTED, result.compile_error
    assert result.stdout.strip() == "42"


@pytest.mark.parametrize("language", NATIVE_PARAMS)
def test_compile_error_is_distinct_from_runtime_error(language):
    result = run(language, BROKEN[language])
    assert result.verdict is Verdict.COMPILE_ERROR
    assert result.compiled is False
    assert result.compile_error


@PYTHON
def test_python_syntax_error_is_reported_not_executed():
    result = run("Python", "def f(:\n    pass\n")
    assert result.verdict is not Verdict.ACCEPTED
    assert "SyntaxError" in result.stderr


@pytest.mark.parametrize("language", LANG_PARAMS)
def test_runtime_error_is_reported(language):
    result = run(language, RUNTIME_THROW[language])
    assert result.verdict is Verdict.RUNTIME_ERROR
    assert result.exit_code != 0


# ── resource limits ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("language", LANG_PARAMS)
def test_infinite_loop_times_out_and_is_killed(language):
    body = {
        "Python": "while True: pass\n",
        "C": "int main(){for(;;);}\n",
        "C++": "int main(){for(;;);}\n",
        "Java": "public class Main{public static void main(String[] a){for(;;);}}\n",
    }[language]
    result = run(language, body)
    assert result.verdict is Verdict.TIMEOUT
    assert result.timed_out is True


@PYTHON
def test_memory_exhaustion_hits_the_memory_limit():
    result = run("Python", "x=[]\nwhile True: x.append(b'a'*10_000_000)\n")
    assert result.verdict is Verdict.MEMORY_LIMIT


@PYTHON
def test_excessive_output_hits_the_output_limit():
    result = run("Python", "import sys\nwhile True:\n    sys.stdout.write('A'*100000); sys.stdout.flush()\n")
    assert result.verdict is Verdict.OUTPUT_LIMIT
    assert result.output_truncated is True
    assert len(result.stdout) <= 1024 * 1024 + 4096


@PYTHON
def test_fork_bomb_is_contained():
    """A fork loop must not escape the pids cgroup, and must not leave the host loaded."""
    result = run("Python", (
        "import os\n"
        "n=0\n"
        "try:\n"
        "    while True:\n"
        "        os.fork(); n+=1\n"
        "except Exception as e:\n"
        "    print('FORK-STOPPED', type(e).__name__, n)\n"
    ))
    assert result.verdict in {Verdict.ACCEPTED, Verdict.RUNTIME_ERROR, Verdict.TIMEOUT, Verdict.MEMORY_LIMIT}
    assert len(result.stdout) < 100_000, "a fork bomb must not produce unbounded output"


# ── isolation ──────────────────────────────────────────────────────────────────────

@PYTHON
def test_host_canary_is_unreadable_from_the_container():
    token = uuid.uuid4().hex
    canary = Path(tempfile.gettempdir()) / f"zhixue_sandbox_canary_{token}.txt"
    canary.write_text("DO_NOT_READ_THIS", encoding="utf-8")
    try:
        code = (
            "import os, glob\n"
            f"p='/tmp/zhixue_sandbox_canary_{token}.txt'\n"
            "print('READ', open(p).read()) if os.path.exists(p) else print('ABSENT')\n"
            "print('CANDIDATES', [q for q in glob.glob('/tmp/*') + glob.glob('/code/*') if 'canary' in q])\n"
        )
        result = run("Python", code)
        assert "DO_NOT_READ_THIS" not in result.stdout
        assert "ABSENT" in result.stdout
    finally:
        canary.unlink(missing_ok=True)


@PYTHON
def test_filesystem_is_read_only_outside_the_run_directory():
    result = run("Python", (
        "for p in ('/code/hacked.txt','/etc/zhixue.txt','/zhixue.txt','/root/zhixue.txt'):\n"
        "    try:\n"
        "        open(p,'w').write('x'); print('WROTE', p)\n"
        "    except Exception as e:\n"
        "        print('DENIED', p, type(e).__name__)\n"
    ))
    assert "WROTE" not in result.stdout
    assert result.stdout.count("DENIED") >= 3


@PYTHON
def test_network_is_unreachable():
    result = run("Python", (
        "import socket\n"
        "socket.setdefaulttimeout(3)\n"
        "for host,port in (('1.1.1.1',80),('127.0.0.1',80),('169.254.169.254',80)):\n"
        "    try:\n"
        "        s=socket.create_connection((host,port),3); print('CONNECTED', host); s.close()\n"
        "    except Exception as e:\n"
        "        print('BLOCKED', host, type(e).__name__)\n"
    ))
    assert "CONNECTED" not in result.stdout
    assert result.stdout.count("BLOCKED") == 3


@PYTHON
def test_host_environment_is_not_visible(monkeypatch):
    monkeypatch.setenv("ZHIXUE_SANDBOX_SECRET", "topsecretvalue")
    result = run("Python", (
        "import os\n"
        "print('LEAK' if os.environ.get('ZHIXUE_SANDBOX_SECRET') else 'CLEAN')\n"
        "print('KEYS', sorted(os.environ))\n"
    ))
    assert "topsecretvalue" not in result.stdout
    assert "CLEAN" in result.stdout


# ── cleanup ────────────────────────────────────────────────────────────────────────

@pytest.mark.skipif(
    IMAGES["C"] in _MISSING or IMAGES["Python"] in _MISSING,
    reason="python/C image not present",
)
def test_no_containers_or_temp_dirs_are_left_behind():
    import subprocess

    before = set(glob.glob(os.path.join(tempfile.gettempdir(), "zhixue_sandbox_*")))
    run("Python", "print('cleanup probe')\n")
    run("C", '#include <stdio.h>\nint main(){printf("cleanup probe\\n");return 0;}\n')
    after = set(glob.glob(os.path.join(tempfile.gettempdir(), "zhixue_sandbox_*")))
    assert after - before == set(), f"temp dirs leaked: {after - before}"

    listing = subprocess.run(
        ["docker", "ps", "-a", "--filter", "name=zhixue-sbx-", "--format", "{{.Names}}"],
        capture_output=True, text=True, timeout=30,
    )
    assert listing.stdout.strip() == "", f"containers leaked: {listing.stdout}"


# ── the command is actually hardened ───────────────────────────────────────────────

def test_docker_command_carries_every_required_isolation_flag():
    cmd = _backend._docker_command(
        "C", ["sh", "-c", "true"], "/tmp/xyz", "zhixue-sbx-test"
    )
    joined = " ".join(cmd)
    for flag in (
        "--network none", "--read-only", "--cap-drop ALL",
        "--security-opt no-new-privileges", "--pids-limit", "--memory",
        "--memory-swap", "--cpus", "--tmpfs",
    ):
        assert flag in joined, f"missing isolation flag: {flag}"
    # None of these may ever appear: they would expose the host.
    for forbidden in ("docker.sock", "--privileged", "-v /:", "-v /etc", "--network host"):
        assert forbidden not in joined, f"forbidden flag present: {forbidden}"
