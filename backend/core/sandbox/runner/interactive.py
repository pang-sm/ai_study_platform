"""Interactive / streaming execution session for the terminals — SECURITY_S0B-P1.

The two WebSocket terminals stream a learner program's real stdin/stdout. That logic used
to run inside the web process (which therefore needed the ``docker`` CLI). It now runs HERE,
inside the least-privileged runner, which owns the rootless daemon.

Nothing about the container is caller-controlled: the argv, image, mounts, tmp dir and
hardening are all fixed by this module. The caller may only send the bounded
``ExecutionRequest`` shape, then raw stdin bytes / eof / interrupt.

Frame contract (runner → web), all JSON text frames:

    {"type":"status","message":str}
    {"type":"compile_error","message":str,"technical_details":str}   # build failed, nothing ran
    {"type":"terminal","data":str}                                   # PTY mode (merged stream)
    {"type":"stdout","data":str} / {"type":"stderr","data":str}      # pipe mode
    {"type":"exit","exit_code":int|null,"timed_out":bool,"stdout":str,"stderr":str}

Web → runner: ``{"type":"stdin","data":str}``, ``{"type":"eof"}``,
``{"type":"interrupt"}`` (alias ``stop``). The runner owns the wall clock and output cap;
the caller cannot extend either.
"""
from __future__ import annotations

import os
import queue
import shutil
import signal
import subprocess
import tempfile
import threading
import time
import uuid
from pathlib import Path

from core.sandbox.docker_backend import (
    _make_container_readable,
    configured_runtime,
    isolation_flags,
    runtime_binary,
)
from core.sandbox.limits import IMAGES, MEMORY_LIMIT, TMPFS_SIZE
from core.sandbox.types import ExecutionRequest, SourceFile

INTERACTIVE_TIMEOUT_SECONDS = 30
COMPILE_TIMEOUT_SECONDS = 20
OUTPUT_CAP_BYTES = 1024 * 1024

_SOURCE_SUFFIXES = {
    "C": (".c",),
    "C++": (".cpp", ".cc", ".cxx"),
}


def _safe_relative(value: str) -> str:
    """Reject absolute / ``..`` paths so a crafted path cannot escape the tmp dir."""
    raw = str(value or "").strip().replace("\\", "/")
    pure = Path(raw)
    if not raw or pure.is_absolute() or ".." in pure.parts:
        raise ValueError(f"unsafe relative path: {value!r}")
    return "/".join(part for part in pure.parts if part not in ("", "."))


class InteractiveSession:
    """One live learner program, run in a one-shot container under the rootless daemon."""

    def __init__(self, request: ExecutionRequest, *, pty: bool = True) -> None:
        self.request = request
        self.language = (request.language or "").strip()
        self.pty = pty
        self.runtime = configured_runtime()
        self.docker = runtime_binary(self.runtime)
        self.tmp_dir = tempfile.mkdtemp(prefix="zhixue-sbx-i-")
        self.container = f"zhixue-sbx-i-{uuid.uuid4().hex[:12]}"

        self._out: "queue.Queue[dict]" = queue.Queue()
        self._proc: subprocess.Popen | None = None
        self._master_fd: int | None = None
        self._readers: list[threading.Thread] = []
        self._collected: list[str] = []
        self._collected_err: list[str] = []
        self._stdin_bytes = 0
        self._stdin_has_newline = False
        self._eof_sent = False
        self._eof_delimiter_added = False
        self._timed_out = False
        self._finished = False
        self._started_at: float | None = None
        self._returncode: int | None = None
        self.compile_failed = False

    # ── preparation ─────────────────────────────────────────────────────────────

    def prepare(self) -> list[dict]:
        """Write the source files and (for native languages) compile. Returns start frames."""
        frames: list[dict] = []
        for item in self.request.files:
            relative = _safe_relative(item.relative_path)
            target = Path(self.tmp_dir) / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(item.content or "", encoding="utf-8")

        # The interactive compile writes the binary into this mounted tree, and the
        # container's user may not own it (see _make_container_readable).
        _make_container_readable(self.tmp_dir, writable=True)

        if self.language in _SOURCE_SUFFIXES:
            frames.extend(self._compile_native())
        return frames

    def _compile_native(self) -> list[dict]:
        suffixes = _SOURCE_SUFFIXES[self.language]
        if self.request.compile_files is not None:
            sources = [s for s in (_safe_relative(p) for p in self.request.compile_files)
                       if s.lower().endswith(suffixes)]
        else:
            sources = [
                _safe_relative(f.relative_path)
                for f in self.request.files
                if f.relative_path.lower().endswith(suffixes)
            ]
        if not sources:
            self.compile_failed = True
            return [{"type": "compile_error", "message": "项目中没有可编译的源文件", "technical_details": ""}]

        compiler = "g++" if self.language == "C++" else "gcc"
        flags = ["-std=c++17", "-O0", "-Wall", "-Wextra"] if self.language == "C++" \
            else ["-std=c11", "-O0", "-Wall", "-Wextra"]
        host_dir = str(Path(self.tmp_dir).resolve()).replace("\\", "/")
        argv = [
            self.docker, "run", "--rm", "--name", f"{self.container}-c",
            *isolation_flags(MEMORY_LIMIT[self.language], runtime=self.runtime),
            "-v", f"{host_dir}:/work", "-w", "/work", "--pull=never",
            IMAGES[self.language], compiler, *flags, *sources, "-o", "program",
        ]
        try:
            proc = subprocess.run(argv, capture_output=True, text=True,
                                  timeout=COMPILE_TIMEOUT_SECONDS)
        except (OSError, subprocess.SubprocessError) as exc:
            self.compile_failed = True
            return [{"type": "compile_error", "message": "编译环境不可用",
                     "technical_details": type(exc).__name__}]
        if proc.returncode != 0:
            raw = (proc.stderr or proc.stdout or "编译失败").strip()
            self.compile_failed = True
            return [{"type": "compile_error", "message": raw[:3000], "technical_details": raw[:8000]}]
        return []

    # ── launch ──────────────────────────────────────────────────────────────────

    def _runtime_argv(self, inner: list[str]) -> list[str]:
        host_dir = str(Path(self.tmp_dir).resolve()).replace("\\", "/")
        memory = MEMORY_LIMIT[self.language]
        tmpfs = f"/tmp:rw,exec,nosuid,size={TMPFS_SIZE[self.language]}"
        return [
            self.docker, "run", "--rm", "-i", "--name", self.container,
            *isolation_flags(memory, runtime=self.runtime),
            "--tmpfs", tmpfs,
            "-v", f"{host_dir}:/code:ro", "-w", "/code", "--pull=never",
            IMAGES[self.language],
            *inner,
        ]

    def _inner(self) -> list[str]:
        if self.language == "Python":
            entry = _safe_relative(self.request.entry_file) if self.request.entry_file else ""
            if not entry:
                entry = next((_safe_relative(f.relative_path) for f in self.request.files
                              if f.relative_path.endswith(".py")), "")
            if not entry:
                raise ValueError("no Python entry file")
            return ["python", "-u", f"/code/{entry}"]
        if self.language in _SOURCE_SUFFIXES:
            return ["/code/program"]     # compiled into the tmp dir by _compile_native
        # Java: compile into the container's tmpfs, then run the selected main class.
        main_class = (self.request.main_class or "Main").strip() or "Main"
        return ["sh", "-lc",
                f"cp -r /code /tmp/work && cd /tmp/work && javac $(find . -name '*.java') && java {main_class}"]

    def start(self) -> None:
        """Launch the container and begin streaming its output."""
        self._started_at = time.time()
        argv = self._runtime_argv(self._inner())
        if self.pty and hasattr(os, "openpty"):
            master, slave = os.openpty()
            self._master_fd = master
            options = {"stdin": slave, "stdout": slave, "stderr": slave, "close_fds": True}
            if os.name == "posix":
                options["start_new_session"] = True
            try:
                self._proc = subprocess.Popen(argv, **options)
            finally:
                os.close(slave)
            self._readers.append(self._spawn_pty_reader())
        else:
            options = {"stdin": subprocess.PIPE, "stdout": subprocess.PIPE,
                       "stderr": subprocess.PIPE, "text": False}
            if os.name == "posix":
                options["start_new_session"] = True
            self._proc = subprocess.Popen(argv, **options)
            self._readers.append(self._spawn_pipe_reader(self._proc.stdout, "stdout", self._collected))
            self._readers.append(self._spawn_pipe_reader(self._proc.stderr, "stderr", self._collected_err))
        threading.Thread(target=self._wait_loop, daemon=True).start()

    def _spawn_pty_reader(self) -> threading.Thread:
        def reader() -> None:
            try:
                while True:
                    chunk = os.read(self._master_fd, 4096)
                    if not chunk:
                        break
                    text = chunk.decode("utf-8", errors="replace")
                    self._collected.append(text)
                    self._out.put({"type": "terminal", "data": text})
            except (OSError, ValueError):
                pass
        thread = threading.Thread(target=reader, daemon=True)
        thread.start()
        return thread

    def _spawn_pipe_reader(self, stream, name: str, sink: list[str]) -> threading.Thread:
        def reader() -> None:
            try:
                while True:
                    chunk = stream.read(4096)
                    if not chunk:
                        break
                    text = chunk.decode("utf-8", errors="replace")
                    sink.append(text)
                    self._out.put({"type": name, "data": text})
            except (OSError, ValueError):
                pass
        thread = threading.Thread(target=reader, daemon=True)
        thread.start()
        return thread

    def _wait_loop(self) -> None:
        proc = self._proc
        if proc is None:
            return
        while proc.poll() is None:
            if self._started_at is not None and time.time() - self._started_at > INTERACTIVE_TIMEOUT_SECONDS:
                self._timed_out = True
                self.interrupt()
                break
            time.sleep(0.05)
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self.interrupt()
        for thread in self._readers:
            thread.join(timeout=2)
        self._returncode = proc.returncode
        self._finished = True
        self._out.put({"type": "__exit__"})

    # ── client input ────────────────────────────────────────────────────────────

    def send_stdin(self, data: str) -> None:
        if self._eof_sent or not data:
            return
        raw = data.encode("utf-8")
        self._stdin_bytes += len(raw)
        self._stdin_has_newline = self._stdin_has_newline or b"\n" in raw or b"\r" in raw
        try:
            if self._master_fd is not None:
                os.write(self._master_fd, raw)
            elif self._proc is not None and self._proc.stdin is not None:
                self._proc.stdin.write(raw)
                self._proc.stdin.flush()
        except (OSError, ValueError):
            pass

    def send_eof(self) -> None:
        if self._eof_sent:
            return
        self._eof_sent = True
        try:
            if self._master_fd is not None:
                # A canonical PTY needs a line delimiter to release a buffered readline
                # before the real Ctrl+D EOF signal.
                if self._stdin_bytes and not self._stdin_has_newline:
                    os.write(self._master_fd, b"\n")
                    self._eof_delimiter_added = True
                os.write(self._master_fd, b"\x04")
            elif self._proc is not None and self._proc.stdin is not None:
                self._proc.stdin.close()
        except (OSError, ValueError):
            pass

    def interrupt(self) -> None:
        proc = self._proc
        if proc is None or proc.poll() is not None:
            return
        try:
            if os.name == "posix":
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            else:
                proc.terminate()
            proc.wait(timeout=2)
        except Exception:
            try:
                if os.name == "posix":
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                else:
                    proc.kill()
            except Exception:
                pass

    # ── output ──────────────────────────────────────────────────────────────────

    def drain(self) -> list[dict]:
        """Pop every frame currently available (non-blocking)."""
        frames: list[dict] = []
        while True:
            try:
                frames.append(self._out.get_nowait())
            except queue.Empty:
                break
        return frames

    @property
    def finished(self) -> bool:
        return self._finished

    def exit_frame(self) -> dict:
        stdout = "".join(self._collected)[:8000]
        stderr = "".join(self._collected_err)[:8000]
        return {
            "type": "exit",
            "exit_code": self._returncode,
            "timed_out": self._timed_out,
            "stdout": stdout,
            "stderr": stderr,
            "eof_delimiter_added": self._eof_delimiter_added,
        }

    def cleanup(self) -> None:
        if self._proc is not None and self._proc.poll() is None:
            self.interrupt()
        if self._master_fd is not None:
            try:
                os.close(self._master_fd)
            except OSError:
                pass
        try:
            subprocess.run([self.docker, "rm", "-f", self.container],
                           capture_output=True, timeout=15)
        except (OSError, subprocess.SubprocessError):
            pass
        shutil.rmtree(self.tmp_dir, ignore_errors=True)
