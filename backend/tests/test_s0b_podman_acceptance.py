"""SECURITY_S0B-P1 — rootless-Podman acceptance against REAL containers.

Skipped unless rootless Podman is available AND the pinned images already exist in the
rootless store (the runtime never auto-pulls). Covers the four languages, every verdict,
stdin/stdout, Java multifile, exit-code mapping, the CPU backstop and container cleanup.
"""
from __future__ import annotations

import glob
import os
import shutil
import subprocess
import tempfile

import pytest

from core.sandbox import docker_backend as db
from core.sandbox.limits import IMAGES
from core.sandbox.types import ExecutionRequest, SourceFile, Verdict

_backend = db.DockerExecutionBackend(runtime="podman")


def _probe() -> tuple[bool, set[str]]:
    try:
        if os.name != "posix" or shutil.which("podman") is None or not _backend.available():
            return False, set()
        return True, set(_backend.missing_images())
    except Exception:  # noqa: BLE001
        return False, set()


_DAEMON, _MISSING = _probe()
pytestmark = pytest.mark.skipif(not _DAEMON, reason="rootless podman not available")

ENTRY = {"Python": "main.py", "C": "main.c", "C++": "main.cpp", "Java": "Main.java"}
LANGS = ["Python", "C", "C++", "Java"]


def needs(language: str):
    return pytest.mark.skipif(IMAGES[language] in _MISSING, reason=f"{IMAGES[language]} not present")


def run(language: str, body: str, stdin: str = "", **kw):
    return _backend.run(ExecutionRequest(
        language=language, files=(SourceFile(ENTRY[language], body),),
        entry_file=ENTRY[language], main_class="Main" if language == "Java" else None,
        stdin=stdin, **kw,
    ))


HELLO = {
    "Python": "import sys\nprint('HELLO', sys.stdin.read().strip())\n",
    "C": '#include <stdio.h>\nint main(){char b[64]={0};if(fgets(b,64,stdin))printf("HELLO %s", b);return 0;}\n',
    "C++": '#include <iostream>\nint main(){std::string s;std::cin>>s;std::cout<<"HELLO "<<s<<std::endl;return 0;}\n',
    "Java": 'import java.util.Scanner;\npublic class Main{public static void main(String[] a){Scanner s=new Scanner(System.in);System.out.println("HELLO "+s.next());}}\n',
}
BROKEN = {"C": "int main(){ return oops(); }\n", "C++": "int main(){ return oops(); }\n",
          "Java": "public class Main{ public static void main(String[] a){ int x = ; } }\n"}
THROW = {"Python": "raise ValueError('boom')\n", "C": "int main(){int*p=0;return *p;}\n",
         "C++": "int main(){int*p=nullptr;return *p;}\n",
         "Java": 'public class Main{public static void main(String[] a){throw new RuntimeException("b");}}\n'}


@pytest.mark.parametrize("language", [pytest.param(l, marks=needs(l)) for l in LANGS])
def test_hello_world_with_stdin(language):
    result = run(language, HELLO[language], stdin="world")
    assert result.verdict is Verdict.ACCEPTED, (language, result.stderr)
    assert "HELLO world" in result.stdout


@pytest.mark.parametrize("language", [pytest.param(l, marks=needs(l)) for l in ["C", "C++", "Java"]])
def test_compile_error_is_distinct(language):
    result = run(language, BROKEN[language])
    assert result.verdict is Verdict.COMPILE_ERROR
    assert result.compiled is False and result.compile_error


@pytest.mark.parametrize("language", [pytest.param(l, marks=needs(l)) for l in LANGS])
def test_runtime_error_is_reported(language):
    result = run(language, THROW[language])
    assert result.verdict is Verdict.RUNTIME_ERROR
    assert result.exit_code != 0


@needs("Java")
def test_java_multifile_compiles_and_runs():
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


@needs("Python")
def test_infinite_loop_times_out():
    result = run("Python", "while True: pass\n")
    assert result.verdict is Verdict.TIMEOUT and result.timed_out is True


@needs("Python")
def test_multithreaded_cpu_bound_program_is_still_bounded():
    body = ("import threading\n"
            "def spin():\n"
            "    while True: pass\n"
            "for _ in range(4): threading.Thread(target=spin, daemon=True).start()\n"
            "while True: pass\n")
    result = run("Python", body)
    assert result.verdict in {Verdict.TIMEOUT, Verdict.MEMORY_LIMIT}


@needs("Python")
def test_multi_subprocess_cpu_bound_program_is_still_bounded():
    body = ("import os\n"
            "for _ in range(8):\n"
            "    if os.fork() == 0:\n"
            "        while True: pass\n"
            "while True: pass\n")
    result = run("Python", body)
    assert result.verdict in {Verdict.TIMEOUT, Verdict.MEMORY_LIMIT, Verdict.RUNTIME_ERROR}


@needs("Python")
def test_memory_limit_is_enforced():
    result = run("Python", "x=[]\nwhile True: x.append(bytearray(50_000_000))\n")
    assert result.verdict is Verdict.MEMORY_LIMIT


@needs("Python")
def test_output_flood_is_bounded_and_refused():
    """The host-side output cap bounds the run, but under rootless Podman the CLI's output
    relay is occasionally slow enough that the in-container wall timeout fires first, so
    either verdict is acceptable. The invariant that MUST hold: the run is never ACCEPTED
    and the captured output stays bounded."""
    result = run("Python", "import sys\nwhile True:\n    sys.stdout.write('A'*1000000); sys.stdout.flush()\n")
    assert result.verdict in {Verdict.OUTPUT_LIMIT, Verdict.TIMEOUT}
    assert result.verdict is not Verdict.ACCEPTED
    assert len(result.stdout) <= 1024 * 1024 + 65536


@needs("Python")
def test_a_program_exiting_125_is_the_learners_error_not_a_runtime_failure():
    """125 is reserved by the CLI, but a program may exit 125 with no runtime marker."""
    result = run("Python", "import sys\nsys.exit(125)\n")
    assert result.verdict is Verdict.RUNTIME_ERROR
    assert result.exit_code == 125


@needs("Python")
def test_a_forged_stderr_marker_cannot_make_a_learner_failure_look_like_infra():
    """A learner may print anything to stderr; it must NOT be able to fake a start failure."""
    result = run("Python",
                 "import sys\nprint('Error: runc create failed', file=sys.stderr)\nsys.exit(126)\n")
    assert result.verdict is Verdict.RUNTIME_ERROR
    assert result.exit_code == 126


@needs("Python")
def test_a_runtime_that_cannot_start_the_container_fails_closed(monkeypatch):
    """A missing image must be INTERNAL_ERROR — never the learner's runtime error."""
    monkeypatch.setitem(db.IMAGES, "Python", "docker.io/library/zhixue-nonexistent-image:0")
    result = _backend.run(ExecutionRequest(
        language="Python", files=(SourceFile("main.py", "print(1)\n"),), entry_file="main.py",
    ))
    assert result.verdict is Verdict.INTERNAL_ERROR
    assert result.verdict is not Verdict.RUNTIME_ERROR
    assert result.verdict is not Verdict.WRONG_ANSWER


@needs("Python")
def test_no_containers_or_temp_dirs_are_left_behind():
    before = set(glob.glob(os.path.join(tempfile.gettempdir(), "zhixue_sandbox_*")))
    run("Python", "print('cleanup probe')\n")
    run("Python", "raise SystemExit(1)\n")
    after = set(glob.glob(os.path.join(tempfile.gettempdir(), "zhixue_sandbox_*")))
    assert after - before == set(), f"temp dirs leaked: {after - before}"
    listing = subprocess.run(
        ["podman", "ps", "-a", "--filter", "name=zhixue-sbx-", "--format", "{{.Names}}"],
        capture_output=True, text=True, timeout=30,
    )
    assert listing.stdout.strip() == "", f"containers leaked: {listing.stdout}"
