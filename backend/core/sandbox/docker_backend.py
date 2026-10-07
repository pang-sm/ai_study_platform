"""Docker-isolated execution backend — SECURITY_S0B.

    USER-CONTROLLED CODE MUST NEVER EXECUTE ON THE HOST. THIS MODULE SPAWNS ONLY `docker`.

The only process the backend itself starts is the ``docker`` CLI. Learner source is
written to a per-run host directory, mounted read-only into a one-shot container, and
compiled and run entirely inside that container. No compiler, interpreter or build
tool ever runs on the host.

Every execution:

    create a temp dir -> write the source -> start a NAMED one-shot container ->
    compile (if the language has a build step) -> run -> capture stdout/stderr/exit ->
    ``docker rm -f`` the container -> delete the temp dir

The container is never reused for a learner's next run. The container name is
generated per invocation so a timeout or output-cap kill can always find and remove
the exact container, even if the CLI was killed first.

If ``docker`` is missing, the daemon is down, the image is absent, or the container
cannot be created or started, the call FAILS CLOSED with ``Verdict.INTERNAL_ERROR``
and no output. There is no host fallback of any kind anywhere in this file.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
from pathlib import Path

from core.sandbox.limits import (
    CLI_TIMEOUT_SLACK_SECONDS,
    COMPILE_FAILED_EXIT,
    COMPILE_TIME_SECONDS,
    CONTAINER_ACQUIRE_TIMEOUT_SECONDS,
    CPU_LIMIT,
    IMAGES,
    KILL_GRACE_SECONDS,
    MAX_CONCURRENT_CONTAINERS,
    MAX_FILE_BYTES,
    MAX_STDIN_BYTES,
    MAX_TOTAL_SOURCE_BYTES,
    MEMORY_LIMIT,
    OUTPUT_CAP_BYTES,
    PIDS_LIMIT,
    PROGRAM_TIME_SECONDS,
    TIMEOUT_EXIT_CODE,
    TMPFS_SIZE,
    WALL_TIME_MS,
)
from core.sandbox.types import CompileResult, ExecutionRequest, ExecutionResult, SourceFile, Verdict


# The process-wide ceiling on simultaneous containers. A single uvicorn process serves
# every request, so a module-level semaphore is the correct scope.
_CONTAINER_SLOTS = threading.Semaphore(MAX_CONCURRENT_CONTAINERS)


def container_semaphore() -> threading.Semaphore:
    """The process-wide container ceiling, shared by one-shot runs and interactive sessions."""
    return _CONTAINER_SLOTS


# Source extensions the compiler is allowed to see, per language.
_SOURCE_SUFFIXES = {
    "C": (".c",),
    "C++": (".cpp", ".cc", ".cxx"),
    "Java": (".java",),
}


def isolation_flags(memory: str, cpu: str = CPU_LIMIT) -> list[str]:
    """The mandatory isolation flags EVERY learner container carries, one-shot or interactive.

    Kept in one place so the interactive terminals cannot drift from the judge: network
    off, root filesystem read-only, all capabilities dropped, no privilege escalation,
    swap disabled (``--memory-swap`` == ``--memory``), bounded pids/cpu/memory.
    """
    return [
        "--network", "none",
        "--read-only",
        "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges",
        "--pids-limit", str(PIDS_LIMIT),
        "--memory", memory,
        "--memory-swap", memory,          # equal to --memory: swap disabled
        "--cpus", cpu,
        "--ulimit", "nofile=256:256",
        "--ulimit", "core=0:0",
    ]


def _normalize_path(value: str) -> str:
    """Validate one relative path and return it with forward slashes.

    Refuses absolute paths and any ``..`` segment so a crafted relative_path cannot
    place a file outside the per-run directory.
    """
    raw = str(value or "").strip().replace("\\", "/")
    if not raw:
        raise ValueError("empty relative path")
    pure = Path(raw)
    if pure.is_absolute() or ".." in pure.parts:
        raise ValueError(f"unsafe relative path: {value!r}")
    return "/".join(part for part in pure.parts if part not in ("", "."))


class DockerExecutionBackend:
    """Runs learner programs inside a locked-down, one-shot Docker container."""

    def __init__(self, docker_binary: str | None = None) -> None:
        self._docker = docker_binary or shutil.which("docker") or "docker"

    # ── availability ────────────────────────────────────────────────────────────

    def available(self) -> bool:
        """True when the CLI exists AND the daemon answers. Cheap enough for a preflight."""
        if not shutil.which(self._docker) and os.path.basename(self._docker) == "docker":
            return False
        try:
            probe = subprocess.run(
                [self._docker, "info", "--format", "{{.ServerVersion}}"],
                capture_output=True,
                text=True,
                timeout=10,
            )
        except (OSError, subprocess.SubprocessError):
            return False
        return probe.returncode == 0 and bool((probe.stdout or "").strip())

    def missing_images(self) -> list[str]:
        """Pinned images the daemon does not have locally. Empty means the pool is ready."""
        missing: list[str] = []
        for image in sorted(set(IMAGES.values())):
            try:
                probe = subprocess.run(
                    [self._docker, "image", "inspect", image],
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
            except (OSError, subprocess.SubprocessError):
                missing.append(image)
                continue
            if probe.returncode != 0:
                missing.append(image)
        return missing

    # ── the one public entry point ──────────────────────────────────────────────

    def run(self, request: ExecutionRequest) -> ExecutionResult:
        """Compile and run ``request`` in isolation, always cleaning up afterwards."""
        language = (request.language or "").strip()
        if language not in IMAGES:
            return ExecutionResult(
                language=language,
                verdict=Verdict.INTERNAL_ERROR,
                internal_error=f"unsupported language: {language!r}",
            )
        if not _CONTAINER_SLOTS.acquire(timeout=CONTAINER_ACQUIRE_TIMEOUT_SECONDS):
            return ExecutionResult(
                language=language,
                verdict=Verdict.INTERNAL_ERROR,
                internal_error="sandbox_concurrency_limit",
            )
        try:
            return self._run_isolated(request, language)
        finally:
            _CONTAINER_SLOTS.release()

    # ── implementation ──────────────────────────────────────────────────────────

    def _run_isolated(self, request: ExecutionRequest, language: str) -> ExecutionResult:
        stdin_bytes = (request.stdin or "").encode("utf-8")
        if len(stdin_bytes) > MAX_STDIN_BYTES:
            return ExecutionResult(
                language=language,
                verdict=Verdict.OUTPUT_LIMIT,
                internal_error="stdin exceeds the sandbox limit",
            )

        prepared: list[SourceFile] = []
        total = 0
        for item in request.files:
            try:
                relative = _normalize_path(item.relative_path)
            except ValueError as exc:
                return ExecutionResult(
                    language=language, verdict=Verdict.INTERNAL_ERROR, internal_error=str(exc)
                )
            body = item.content or ""
            size = len(body.encode("utf-8"))
            if size > MAX_FILE_BYTES:
                return ExecutionResult(
                    language=language,
                    verdict=Verdict.OUTPUT_LIMIT,
                    internal_error=f"source file {relative!r} exceeds the size limit",
                )
            total += size
            if total > MAX_TOTAL_SOURCE_BYTES:
                return ExecutionResult(
                    language=language,
                    verdict=Verdict.OUTPUT_LIMIT,
                    internal_error="total source exceeds the size limit",
                )
            prepared.append(SourceFile(relative_path=relative, content=body))

        try:
            inner = self._inner_script(language, request, prepared)
        except ValueError as exc:
            return ExecutionResult(
                language=language, verdict=Verdict.INTERNAL_ERROR, internal_error=str(exc)
            )

        tmp_dir = tempfile.mkdtemp(prefix="zhixue_sandbox_")
        container = f"zhixue-sbx-{uuid.uuid4().hex[:16]}"
        try:
            for item in prepared:
                target = Path(tmp_dir) / item.relative_path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(item.content, encoding="utf-8")
            return self._exec_container(language, request, inner, tmp_dir, container, stdin_bytes)
        finally:
            self._remove_container(container)
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def _inner_script(self, language: str, request: ExecutionRequest, files: list[SourceFile]) -> list[str]:
        """The argv the container runs, with ``/code`` as the read-only source root."""
        if language == "Python":
            entry = _normalize_path(request.entry_file) if request.entry_file else ""
            if not entry:
                entry = next((f.relative_path for f in files if f.relative_path.endswith(".py")), "")
            if not entry:
                raise ValueError("no Python entry file")
            if request.compile_only:
                # Syntax check only — never executes the learner's program.
                return ["timeout", "-k", "1", str(COMPILE_TIME_SECONDS), "python", "-m", "py_compile", entry]
            # No shell needed: ``timeout`` is the container's entry process.
            return ["timeout", "-k", "1", str(PROGRAM_TIME_SECONDS), "python", "-u", entry]

        suffixes = _SOURCE_SUFFIXES[language]
        if request.compile_files is not None:
            sources = [s for s in (_normalize_path(p) for p in request.compile_files)
                       if s.lower().endswith(suffixes)]
        else:
            sources = [f.relative_path for f in files if f.relative_path.lower().endswith(suffixes)]
        if not sources:
            raise ValueError(f"no {language} source files to compile")

        # Compiler flags deliberately match the legacy judge exactly (no -O): the
        # validated catalogue's verdicts were produced with these, so the sandbox must
        # not silently re-grade 240 exercises under different optimisation.
        if language == "C":
            if request.compile_only:
                # Syntax check only: emit the compiler's own diagnostics (warnings too)
                # and let its exit status speak. Runs nothing.
                return ["sh", "-c",
                        f"timeout -k 1 {COMPILE_TIME_SECONDS} gcc -std=c11 -Wall -Wextra -fsyntax-only "
                        f"{' '.join(sources)} 2>&1"]
            compile_cmd = f"timeout -k 1 {COMPILE_TIME_SECONDS} gcc -std=c11 -Wall -Wextra -o /tmp/prog {' '.join(sources)}"
            return ["sh", "-c", self._wrap(compile_cmd, self._run_wrapped(["/tmp/prog"]))]

        if language == "C++":
            if request.compile_only:
                return ["sh", "-c",
                        f"timeout -k 1 {COMPILE_TIME_SECONDS} g++ -std=c++17 -Wall -Wextra -fsyntax-only "
                        f"{' '.join(sources)} 2>&1"]
            compile_cmd = f"timeout -k 1 {COMPILE_TIME_SECONDS} g++ -std=c++17 -Wall -Wextra -o /tmp/prog {' '.join(sources)}"
            return ["sh", "-c", self._wrap(compile_cmd, self._run_wrapped(["/tmp/prog"]))]

        # Java: compile into a writable copy on tmpfs, then run the selected main class.
        # The classpath is absolute so the run does not depend on a preceding ``cd``.
        main_class = (request.main_class or "").strip()
        if not main_class:
            raise ValueError("Java requires a main class")
        # Only ``javac`` is time-limited, and only after the copy — the ``$(find ...)``
        # must expand in /tmp/work, so it stays inside this one shell string.
        compile_cmd = (
            "mkdir -p /tmp/work && cp -a /code/. /tmp/work && cd /tmp/work && "
            f"timeout -k 1 {COMPILE_TIME_SECONDS} javac -encoding UTF-8 $(find . -name '*.java')"
        )
        if request.compile_only:
            return ["sh", "-c", self._wrap(compile_cmd, "true")]
        run_cmd = self._run_wrapped([f"java -Dfile.encoding=UTF-8 -Xmx256m -cp /tmp/work {main_class}"])
        return ["sh", "-c", self._wrap(compile_cmd, run_cmd)]

    @staticmethod
    def _run_wrapped(argv: list[str]) -> str:
        """Run the program under the in-container wall limit so the verdict is honest."""
        return f"timeout -k 1 {PROGRAM_TIME_SECONDS} " + " ".join(argv)

    @staticmethod
    def _wrap(compile_cmd: str, run_cmd: str) -> str:
        """Compile (already time-bounded), then exec the run. Exit 101 means "did not build"."""
        return (
            f"{compile_cmd} 2>/tmp/zhixue_compile_err; "
            "rc=$?; "
            "if [ $rc -ne 0 ]; then cat /tmp/zhixue_compile_err >&2; exit 101; fi; "
            f"exec {run_cmd}"
        )

    def _docker_command(
        self, language: str, inner: list[str], tmp_dir: str, container: str
    ) -> list[str]:
        """The hardened ``docker run``. Every isolation flag is mandatory, not optional."""
        # Docker Desktop on Windows needs a forward-slash, absolute host path.
        host_dir = str(Path(tmp_dir).resolve()).replace("\\", "/")
        memory = MEMORY_LIMIT[language]
        return [
            self._docker, "run",
            "--name", container,
            *isolation_flags(memory),
            "--tmpfs", f"/tmp:rw,exec,nosuid,nodev,size={TMPFS_SIZE[language]}",
            "-v", f"{host_dir}:/code:ro",
            "-w", "/code",
            "-i",
            # Never pull at run time. A missing image must fail fast and closed (the
            # preflight is what guarantees the pool is present), not trigger a surprise
            # network fetch that also hides the failure behind a wall-timeout.
            "--pull", "never",
            IMAGES[language],
            *inner,
        ]

    def _exec_container(
        self,
        language: str,
        request: ExecutionRequest,
        inner: list[str],
        tmp_dir: str,
        container: str,
        stdin_bytes: bytes,
    ) -> ExecutionResult:
        wall_ms = request.wall_time_ms or WALL_TIME_MS[language]
        cmd = self._docker_command(language, inner, tmp_dir, container)
        started = time.time()

        try:
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except FileNotFoundError:
            return ExecutionResult(
                language=language,
                verdict=Verdict.INTERNAL_ERROR,
                internal_error="docker CLI not found",
            )
        except OSError as exc:
            return ExecutionResult(
                language=language,
                verdict=Verdict.INTERNAL_ERROR,
                internal_error=f"docker CLI could not start: {type(exc).__name__}",
            )

        out_buf = bytearray()
        err_buf = bytearray()
        state = {"killed_for_output": False, "killed_for_time": False}

        def _kill() -> None:
            # Kill the CLI promptly. This MUST NOT block: a reader thread calling
            # ``docker rm -f`` here would stall the cap/timeout path for the whole CLI
            # timeout. The container itself is force-removed in the ``finally`` below,
            # which is what actually stops a program whose CLI we just killed.
            try:
                proc.kill()
            except OSError:
                pass

        def _pump(stream, sink: bytearray, limit: int) -> None:
            try:
                while True:
                    chunk = stream.read(4096)
                    if not chunk:
                        break
                    room = limit - len(sink)
                    if room <= 0:
                        state["killed_for_output"] = True
                        _kill()
                        break
                    sink.extend(chunk[:room])
                    if len(chunk) > room:
                        state["killed_for_output"] = True
                        _kill()
                        break
            except (OSError, ValueError):
                pass
            finally:
                try:
                    stream.close()
                except OSError:
                    pass

        writer = threading.Thread(target=self._feed_stdin, args=(proc, stdin_bytes), daemon=True)
        out_reader = threading.Thread(target=_pump, args=(proc.stdout, out_buf, OUTPUT_CAP_BYTES), daemon=True)
        err_reader = threading.Thread(target=_pump, args=(proc.stderr, err_buf, OUTPUT_CAP_BYTES), daemon=True)
        writer.start()
        out_reader.start()
        err_reader.start()

        deadline = started + wall_ms / 1000.0
        while proc.poll() is None:
            if time.time() > deadline:
                state["killed_for_time"] = True
                _kill()
                break
            time.sleep(0.02)

        try:
            proc.wait(timeout=max(1.0, KILL_GRACE_SECONDS))
        except subprocess.TimeoutExpired:
            _kill()
            try:
                proc.wait(timeout=KILL_GRACE_SECONDS)
            except subprocess.TimeoutExpired:
                pass
        out_reader.join(timeout=2)
        err_reader.join(timeout=2)
        writer.join(timeout=2)

        duration_ms = int((time.time() - started) * 1000)
        exit_code = proc.returncode
        stdout = out_buf.decode("utf-8", errors="replace")
        stderr = err_buf.decode("utf-8", errors="replace")
        truncated = state["killed_for_output"]

        # Output-cap is checked first: a program that floods stdout trips the cap within
        # milliseconds, well before the wall deadline, so reporting TIMEOUT for it would
        # misdescribe what actually happened.
        if truncated:
            return ExecutionResult(
                language=language,
                verdict=Verdict.OUTPUT_LIMIT,
                stdout=stdout,
                stderr=stderr,
                exit_code=exit_code,
                duration_ms=duration_ms,
                output_truncated=True,
            )
        if state["killed_for_time"]:
            return ExecutionResult(
                language=language,
                verdict=Verdict.TIMEOUT,
                stdout=stdout,
                stderr=stderr,
                exit_code=exit_code,
                duration_ms=duration_ms,
                timed_out=True,
                output_truncated=truncated,
            )
        if exit_code == COMPILE_FAILED_EXIT:
            return ExecutionResult(
                language=language,
                verdict=Verdict.COMPILE_ERROR,
                duration_ms=duration_ms,
                compile=CompileResult(ok=False, diagnostic=stderr.strip() or "编译失败"),
                exit_code=exit_code,
            )
        if exit_code == TIMEOUT_EXIT_CODE:
            # The in-container ``timeout`` stopped the program at its own wall limit.
            return ExecutionResult(
                language=language,
                verdict=Verdict.TIMEOUT,
                stdout=stdout,
                stderr=stderr,
                exit_code=exit_code,
                duration_ms=duration_ms,
                timed_out=True,
            )
        if exit_code == 137:
            # SIGKILL: the cgroup OOM killer, since time/output kills are handled above.
            return ExecutionResult(
                language=language,
                verdict=Verdict.MEMORY_LIMIT,
                stdout=stdout,
                stderr=stderr,
                exit_code=exit_code,
                duration_ms=duration_ms,
            )
        if exit_code != 0:
            return ExecutionResult(
                language=language,
                verdict=Verdict.RUNTIME_ERROR,
                stdout=stdout,
                stderr=stderr,
                exit_code=exit_code,
                duration_ms=duration_ms,
            )
        return ExecutionResult(
            language=language,
            verdict=Verdict.ACCEPTED,
            stdout=stdout,
            stderr=stderr,
            exit_code=exit_code,
            duration_ms=duration_ms,
        )

    @staticmethod
    def _feed_stdin(proc, payload: bytes) -> None:
        try:
            if payload:
                proc.stdin.write(payload)
            proc.stdin.close()
        except (OSError, ValueError, AttributeError):
            pass

    def _remove_container(self, container: str) -> None:
        """Force-remove the container. Idempotent; safe when it was never created."""
        try:
            subprocess.run(
                [self._docker, "rm", "-f", container],
                capture_output=True,
                text=True,
                timeout=KILL_GRACE_SECONDS + CLI_TIMEOUT_SLACK_SECONDS,
            )
        except (OSError, subprocess.SubprocessError):
            pass
