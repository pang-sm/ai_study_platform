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
import select
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
    CPU_TIME_LIMIT_SECONDS,
    IMAGES,
    KILL_GRACE_SECONDS,
    MAX_CONCURRENT_CONTAINERS,
    MAX_FILE_BYTES,
    MAX_STDIN_BYTES,
    MAX_TOTAL_SOURCE_BYTES,
    MEMORY_LIMIT,
    OUTPUT_CAP_BYTES,
    OUTPUT_FIFO_MODE,
    OUTPUT_MOUNT_DIR,
    PIDS_LIMIT,
    PODMAN_CONTAINER_USER,
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


# The container CLI the sandbox drives. Docker and rootless Podman share the SAME protocol,
# limits, result types and hardening — only the CLI binary and the CPU-limit mechanism
# differ. The deployment selects one; there is no second sandbox implementation.
CONTAINER_RUNTIME_ENV = "SANDBOX_CONTAINER_RUNTIME"
RUNTIME_DOCKER = "docker"
RUNTIME_PODMAN = "podman"
_SUPPORTED_RUNTIMES = (RUNTIME_DOCKER, RUNTIME_PODMAN)


def configured_runtime() -> str:
    """The container runtime to drive: ``docker`` (default) or ``podman``."""
    raw = (os.environ.get(CONTAINER_RUNTIME_ENV) or RUNTIME_DOCKER).strip().lower()
    return raw if raw in _SUPPORTED_RUNTIMES else RUNTIME_DOCKER


def runtime_binary(runtime: str | None = None) -> str:
    """The CLI binary for a runtime. Both accept the same ``run`` argv."""
    return runtime or configured_runtime()


# Exit codes docker/podman reserve for a failure of the CLI/daemon ITSELF. A learner
# program may also legitimately exit 125/126/127 (verified against rootless Podman), so
# the code alone is NOT decisive. The decision is made from the RUNTIME's own record of the
# container (see DockerExecutionBackend._container_state) — NEVER from the learner's output,
# which is untrusted and trivially forgeable.
_RUNTIME_FAILURE_EXIT_CODES = (125, 126, 127)

# Container states that mean "the container will not produce output any more": a container
# that never STARTED (`created`/`configured`) or that has EXITED. Only `exited` means the
# program actually ran inside it.
_TERMINAL_CONTAINER_STATES = ("created", "configured", "exited")


def _is_container_start_failure(state: tuple[str, int | None] | None) -> bool:
    """True when a 125/126/127 exit is a container-start failure rather than the program's.

    ``state`` is the runtime's own ``(status, exit_code)`` for the container, or ``None``
    when the runtime created no container at all (e.g. a missing image). Both of those are
    container-start failures; only ``exited`` means the learner's program ran and chose the
    exit code itself.
    """
    return state is None or state[0] != "exited"


def isolation_flags(memory: str, cpu: str = CPU_LIMIT, *, runtime: str | None = None) -> list[str]:
    """The mandatory isolation flags EVERY learner container carries, one-shot or interactive.

    Kept in one place so the interactive terminals cannot drift from the judge: network
    off, root filesystem read-only, all capabilities dropped, no privilege escalation,
    swap disabled (``--memory-swap`` == ``--memory``), bounded pids/memory and a bounded CPU.

    The CPU bound differs by runtime: Docker sets a cgroup CPU **quota** (``--cpus``);
    rootless Podman cannot (the ``cpu`` cgroup controller is not delegated to user
    sessions), so it uses a per-process cumulative CPU-time **backstop** instead
    (``--ulimit cpu`` = RLIMIT_CPU). That backstop is weaker than a quota — see
    ``limits.CPU_TIME_LIMIT_SECONDS``.
    """
    rt = runtime or configured_runtime()
    flags = [
        "--network", "none",
        "--read-only",
        "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges",
        "--pids-limit", str(PIDS_LIMIT),
        "--memory", memory,
        "--memory-swap", memory,          # equal to --memory: swap disabled
    ]
    if rt == RUNTIME_PODMAN:
        flags += ["--ulimit", f"cpu={CPU_TIME_LIMIT_SECONDS}:{CPU_TIME_LIMIT_SECONDS}"]
        # Disk-safety: podman otherwise duplicates the container's stdout into the systemd
        # journal (default `journald`) or a per-container `ctr.log` (`k8s-file`). The runner
        # already captures stdout through the pipe, so an unbounded learner print loop would
        # fill the host disk with a second, uncapped copy (observed: GB-scale growth).
        flags += ["--log-driver=none"]
        # Podman forwards the host's HTTP_PROXY/HTTPS_PROXY/NO_PROXY into containers by
        # default. The sandbox user's containers.conf sets `http_proxy = false` as a second
        # layer, but the argv must carry it explicitly so the guarantee does not depend on
        # host config that a caller could change.
        flags += ["--http-proxy=false"]
        # Rootless Podman maps the container's root onto the runner's own uid, which would
        # make it the FIFO's OWNER and so able to READ the trusted output channel. A
        # non-owner uid restores write-only access (see limits.OUTPUT_FIFO_MODE).
        flags += ["--user", PODMAN_CONTAINER_USER]
    else:
        flags += ["--cpus", cpu]
    flags += ["--ulimit", "nofile=256:256", "--ulimit", "core=0:0"]
    return flags


def _make_container_readable(root: str, *, writable: bool = False) -> None:
    """Make the per-run tree traversable/readable by the container's user.

    ``tempfile.mkdtemp`` creates a 0700 directory owned by the calling user. A rootful
    Docker container runs as its own root, but the hardened argv drops ALL capabilities —
    including ``CAP_DAC_OVERRIDE`` — so that user cannot traverse a 0700 directory it does
    not own, and every run fails with ``Permission denied``. Rootless Podman hides the bug
    because it maps the container's uid onto the owning host user. Normalising the tree
    (dirs 0711 = traverse-only, files 0644) lets both runtimes read it.

    ``writable`` widens the modes so a container can WRITE into the tree — needed only by
    the interactive path, whose compile step emits the binary into the mounted directory.
    The tree is deleted immediately after the run.
    """
    dir_mode = 0o777 if writable else 0o755
    file_mode = 0o666 if writable else 0o644
    os.chmod(root, dir_mode)
    for dirpath, dirnames, filenames in os.walk(root):
        for name in dirnames:
            os.chmod(os.path.join(dirpath, name), dir_mode)
        for name in filenames:
            os.chmod(os.path.join(dirpath, name), file_mode)


def _prepare_output_files(tmp_dir: str) -> None:
    """Create the two FIFOs the container's stdout/stderr are redirected into.

    The host opens the read end and is the ONLY reader of the trusted channel. Mode 0602
    leaves the container write-only, and the container is never the FIFO's owner (rootful
    Docker runs as a capability-stripped non-owner root; rootless Podman runs as
    ``PODMAN_CONTAINER_USER``), so a learner can write the stream but cannot read it, become
    a second reader, or chmod it.
    """
    for name in ("out.stdout", "out.stderr"):
        path = os.path.join(tmp_dir, name)
        if os.path.exists(path):
            os.unlink(path)
        os.mkfifo(path, OUTPUT_FIFO_MODE)
        os.chmod(path, OUTPUT_FIFO_MODE)


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
    """Runs learner programs inside a locked-down, one-shot container.

    The name is historical: this drives whichever container CLI the deployment selected
    (Docker or rootless Podman) through ONE shared, hardened protocol. There is no second
    sandbox implementation and no per-runtime business logic.
    """

    def __init__(self, docker_binary: str | None = None, *, runtime: str | None = None) -> None:
        self._runtime = runtime or configured_runtime()
        self._docker = docker_binary or shutil.which(self._runtime) or self._runtime

    @property
    def runtime(self) -> str:
        return self._runtime

    # ── availability ────────────────────────────────────────────────────────────

    def available(self) -> bool:
        """True when the CLI exists AND the runtime answers. Cheap enough for a preflight."""
        if not shutil.which(self._docker) and os.path.basename(self._docker) == self._runtime:
            return False
        if self._runtime == RUNTIME_PODMAN:
            probe_args = ["version", "--format", "{{.Version}}"]
        else:
            probe_args = ["info", "--format", "{{.ServerVersion}}"]
        try:
            probe = subprocess.run(
                [self._docker, *probe_args],
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
            # Order matters: normalise the tree first, THEN make the two output files
            # world-writable — the tree walk would otherwise reset them to 0644 and a
            # capability-stripped Docker container could not write them.
            _make_container_readable(tmp_dir)
            _prepare_output_files(tmp_dir)
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
                return ["sh", "-c", self._redirect(
                    f"timeout -k 1 {COMPILE_TIME_SECONDS} python -m py_compile {entry}")]
            return ["sh", "-c", self._redirect(
                f"timeout -k 1 {PROGRAM_TIME_SECONDS} python -u {entry}")]

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
                        f"{' '.join(sources)} >{OUTPUT_MOUNT_DIR}/stdout 2>&1"]
            compile_cmd = f"timeout -k 1 {COMPILE_TIME_SECONDS} gcc -std=c11 -Wall -Wextra -o /tmp/prog {' '.join(sources)}"
            return ["sh", "-c", self._wrap(compile_cmd, self._run_wrapped(["/tmp/prog"]))]

        if language == "C++":
            if request.compile_only:
                return ["sh", "-c",
                        f"timeout -k 1 {COMPILE_TIME_SECONDS} g++ -std=c++17 -Wall -Wextra -fsyntax-only "
                        f"{' '.join(sources)} >{OUTPUT_MOUNT_DIR}/stdout 2>&1"]
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
            # ``cp -r`` (not ``-a``): preserving ownership needs CAP_CHOWN, which
            # ``--cap-drop ALL`` removes, so ``cp -a`` fails under rootful Docker.
            "mkdir -p /tmp/work && cp -r /code/. /tmp/work && cd /tmp/work && "
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
    def _redirect(cmd: str) -> str:
        """Run ``cmd`` with stdout/stderr going to the two host-read FIFOs.

        The bound is the host's own byte count + kill; RLIMIT_FSIZE is deliberately NOT used
        (it does not bound a FIFO's total output).
        """
        out = OUTPUT_MOUNT_DIR
        return f"exec {cmd} >{out}/stdout 2>{out}/stderr"

    @staticmethod
    def _wrap(compile_cmd: str, run_cmd: str) -> str:
        """Compile (already time-bounded), then exec the run. Exit 101 means "did not build".

        Both phases write to the host-read FIFOs, so capture never depends on the container
        CLI's relay and the compile diagnostic is what the host reads on exit 101.
        """
        out = OUTPUT_MOUNT_DIR
        return (
            f"{compile_cmd} >{out}/stdout 2>{out}/stderr; "
            "rc=$?; "
            "if [ $rc -ne 0 ]; then exit 101; fi; "
            f"exec {run_cmd} >{out}/stdout 2>{out}/stderr"
        )

    def _docker_command(
        self, language: str, inner: list[str], tmp_dir: str, container: str
    ) -> list[str]:
        """The hardened ``<runtime> run``. Every isolation flag is mandatory, not optional."""
        # Docker Desktop on Windows needs a forward-slash, absolute host path.
        host_dir = str(Path(tmp_dir).resolve()).replace("\\", "/")
        memory = MEMORY_LIMIT[language]
        return [
            self._docker, "run",
            "--name", container,
            *isolation_flags(memory, runtime=self._runtime),
            "--tmpfs", f"/tmp:rw,exec,nosuid,nodev,size={TMPFS_SIZE[language]}",
            "-v", f"{host_dir}:/code:ro",
            # stdout/stderr are captured through these two FILES, never the CLI's
            # attached-output relay (rootless Podman truncates that).
            "-v", f"{host_dir}/out.stdout:{OUTPUT_MOUNT_DIR}/stdout:rw",
            "-v", f"{host_dir}/out.stderr:{OUTPUT_MOUNT_DIR}/stderr:rw",
            "-w", "/code",
            "-i",
            # Never pull at run time. A missing image must fail fast and closed (the
            # preflight is what guarantees the pool is present), not trigger a surprise
            # network fetch that also hides the failure behind a wall-timeout.
            "--pull=never",
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
                # The container's stdout/stderr go to the two mounted files, so the CLI's
                # own streams carry nothing we judge on — discard them so a chatty CLI can
                # never block the run.
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
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

        state = {"killed_for_time": False, "killed_for_output": False}
        stop = threading.Event()
        out_buf: bytearray = bytearray()
        err_buf: bytearray = bytearray()

        def _kill() -> None:
            # Kill the CLI promptly; the container itself is force-removed in the
            # ``finally``, which is what actually stops a program whose CLI we just killed.
            try:
                proc.kill()
            except OSError:
                pass

        def _drain(fd: int, sink: bytearray) -> None:
            """Drain one FIFO into a capped buffer; kill the run once the cap is exceeded.

            The host is the ONLY reader of this channel, so these bytes are the trusted
            count — a learner cannot truncate a FIFO nor become a second reader.

            A zero-length read on a FIFO means "every writer has closed" ONLY once a writer
            has actually been seen: before the container opens the write end, read(2) also
            returns 0, and treating that as EOF would abandon capture before the program
            ever ran.
            """
            saw_data = False
            while not stop.is_set():
                try:
                    ready, _, _ = select.select([fd], [], [], 0.05)
                except (OSError, ValueError):
                    return
                if not ready:
                    continue
                try:
                    chunk = os.read(fd, 65536)
                except (OSError, ValueError):
                    continue
                if not chunk:
                    if saw_data:                   # EOF: every writer has closed
                        return
                    continue                       # no writer yet — not EOF
                saw_data = True
                room = OUTPUT_CAP_BYTES - len(sink)
                if room <= 0 or len(chunk) > room:  # a byte beyond the cap arrived
                    sink.extend(chunk[:max(room, 0)])
                    state["killed_for_output"] = True
                    _kill()
                    return
                sink.extend(chunk)

        fds: list[int] = []
        readers: list[threading.Thread] = []
        try:
            for name, sink in (("out.stdout", out_buf), ("out.stderr", err_buf)):
                fd = os.open(os.path.join(tmp_dir, name), os.O_RDONLY | os.O_NONBLOCK)
                fds.append(fd)
                thread = threading.Thread(target=_drain, args=(fd, sink), daemon=True)
                thread.start()
                readers.append(thread)
        except OSError as exc:
            for fd in fds:
                try:
                    os.close(fd)
                except OSError:
                    pass
            return ExecutionResult(
                language=language,
                verdict=Verdict.INTERNAL_ERROR,
                internal_error=f"output channel unavailable: {type(exc).__name__}",
            )

        writer = threading.Thread(target=self._feed_stdin, args=(proc, stdin_bytes), daemon=True)
        writer.start()

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
        writer.join(timeout=2)

        # Let the readers observe EOF, then stop them and release the fds. The over-limit
        # decision is the host's OWN byte count on the trusted channel.
        for thread in readers:
            thread.join(timeout=2)
        stop.set()
        for fd in fds:
            try:
                os.close(fd)
            except OSError:
                pass
        for thread in readers:
            thread.join(timeout=1)

        duration_ms = int((time.time() - started) * 1000)
        exit_code = proc.returncode
        truncated = state["killed_for_output"]
        stdout = bytes(out_buf[:OUTPUT_CAP_BYTES]).decode("utf-8", errors="replace")
        stderr = bytes(err_buf[:OUTPUT_CAP_BYTES]).decode("utf-8", errors="replace")

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
        if exit_code in _RUNTIME_FAILURE_EXIT_CODES and _is_container_start_failure(
            self._container_state(container)
        ):
            # The runtime never ran the learner's program (bad image, failed init, ...).
            # Fail CLOSED and never surface the runtime's reason as the learner's error.
            # Decided from the runtime's own container record, NOT from learner output.
            return ExecutionResult(
                language=language,
                verdict=Verdict.INTERNAL_ERROR,
                stdout=stdout,
                stderr="",
                exit_code=exit_code,
                duration_ms=duration_ms,
                internal_error="container_runtime_failure",
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

    def _container_state(self, container: str) -> tuple[str, int | None] | None:
        """The runtime's OWN record of a container: ``(status, exit_code)``, or None if absent.

        This is the authoritative, NON-spoofable answer to "did the container run?" — it is
        read from the runtime's state store, never from the learner's output, so a learner
        cannot forge it. Returns None when no such container exists (the runtime never
        created it, e.g. a missing image).
        """
        last: tuple[str, int | None] | None = None
        for _ in range(4):
            try:
                probe = subprocess.run(
                    [self._docker, "inspect", "--format",
                     "{{.State.Status}} {{.State.ExitCode}}", container],
                    capture_output=True, text=True, timeout=CLI_TIMEOUT_SLACK_SECONDS,
                )
            except (OSError, subprocess.SubprocessError):
                return last
            if probe.returncode != 0:
                return last                          # no such container
            parts = (probe.stdout or "").strip().split()
            if len(parts) != 2:
                return last
            try:
                code: int | None = int(parts[1])
            except ValueError:
                code = None
            last = (parts[0], code)
            if parts[0] in _TERMINAL_CONTAINER_STATES:
                return last
            time.sleep(0.2)                          # running/stopping: let it settle
        return last

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
