"""P6.1 §C/§D/§H — the ONE canonical authenticated E2E backend harness.

WHAT IT IS
----------
Test infrastructure, not a product feature. It brings up the REAL backend (``main:app``) on an
isolated database with a fake provider, seeded product state and a learner that logs in
through the real session contract — so an authenticated browser (Playwright) can exercise the
product end to end without touching anything real.

ONE COMMAND
-----------
    cd backend
    ./.venv/Scripts/python.exe scripts/e2e_harness.py --json
    (or: python scripts/e2e_harness.py --json)

It prints ONE line of JSON (the bootstrap contract), then serves until it is stopped:

    {"base_url": "http://127.0.0.1:49999", "port": 49999, "username": "e2e_learner",
     "password": "…", "database_url": "sqlite:///…/e2e.db", "data_origin": "ACCEPTANCE",
     "temp_dir": "…", "health": "http://127.0.0.1:49999/api/health", "pid": 12345}

The frontend consumes it WITHOUT any source change (``VITE_API_BASE_URL`` is the app's own
environment contract):

    VITE_API_BASE_URL=http://127.0.0.1:49999 npm run dev      # then run Playwright

WHAT IT GUARANTEES
------------------
* a fresh temp directory per run (``mktemp``-style), removed on shutdown;
* ``DATABASE_URL`` pointing INSIDE that directory — ``backend/app.db`` can never be opened;
* ``alembic upgrade head`` against that database before anything starts;
* ``APP_ENV=acceptance`` and ``DATA_ORIGIN=ACCEPTANCE``, so every fact this run records is
  marked as an acceptance rehearsal and can never satisfy a training-readiness gate;
* the FakeProvider injected at the ONE provider seam (never an HTTP mock), so every AI call
  still travels capability → permission → usage → router → orchestrator → ``ai_requests``;
* a real learner created with a real password, logging in through ``POST /login``;
* deterministic shutdown: only the process it started is terminated, the temp dir is removed.

WHAT IT REFUSES
---------------
Production credentials, a paid provider, real user data, ``backend/app.db``.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent

DEFAULT_USERNAME = "e2e_learner"
DEFAULT_PASSWORD = "e2e-learner-pass-1"
HEALTH_TIMEOUT_SECONDS = 90


def free_port() -> int:
    """An unused loopback port (the OS picks it; we release it immediately)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _wait_for_health(base_url: str, process: subprocess.Popen | None = None,
                     timeout: float = HEALTH_TIMEOUT_SECONDS) -> bool:
    """The health-ready signal: poll /api/health until it answers 200."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if process is not None and process.poll() is not None:
            return False
        try:
            with urllib.request.urlopen(f"{base_url}/api/health", timeout=2) as response:
                if response.status == 200:
                    return True
        except (urllib.error.URLError, OSError, TimeoutError):
            time.sleep(0.35)
    return False


class E2EEnvironment:
    """One isolated, authenticated, fake-provider backend — and nothing else.

    Usable as a context manager:

        with E2EEnvironment() as env:
            requests.get(f"{env.base_url}/api/health")      # a REAL server
            # env.username / env.password for the real login
    """

    def __init__(self, *, username: str = DEFAULT_USERNAME, password: str = DEFAULT_PASSWORD,
                 tier: str = "standard", port: int | None = None,
                 data_origin: str = "ACCEPTANCE", app_env: str = "acceptance",
                 python_executable: str | None = None, keep: bool = False):
        self.username = username
        self.password = password
        self.tier = tier
        self.port = port or 0
        self.data_origin = data_origin
        self.app_env = app_env
        self.keep = keep
        self.python = python_executable or sys.executable
        self.temp_dir: Path | None = None
        self.database_url = ""
        self.process: subprocess.Popen | None = None
        self.base_url = ""
        self.seed_identity: dict = {}
        self.log_path: Path | None = None
        self.heartbeat_path: Path | None = None
        self._heartbeat_stop = threading.Event()
        self._heartbeat_thread: threading.Thread | None = None
        self._log_handle = None

    # ---- environment ----

    def _child_env(self) -> dict:
        env = dict(os.environ)
        env.update({
            "DATABASE_URL": self.database_url,
            "UPLOAD_ROOT": str(Path(self.temp_dir) / "uploads"),
            "APP_ENV": self.app_env,
            "DATA_ORIGIN": self.data_origin,
            # A single-process, single-worker test server; the SHADOW pipeline stays as
            # configured for tests so the product's default behaviour is exercised.
            "STUDENT_TWIN_MODE": env.get("STUDENT_TWIN_MODE", "internal"),
            "AI_SESSION_COOKIE_SECURE": "false",
        })
        # Never inherit a real provider credential into the harness process.
        for key in list(env):
            if key.endswith("_API_KEY") or key in {"PAYMENT_PROVIDER"}:
                env.pop(key, None)
        return env

    # ---- lifecycle ----

    def start(self) -> "E2EEnvironment":
        self.temp_dir = Path(tempfile.mkdtemp(prefix="zhixue-e2e-"))
        self.database_url = f"sqlite:///{(self.temp_dir / 'e2e.db').as_posix()}"
        self.log_path = self.temp_dir / "server.log"
        if not self.port:
            self.port = free_port()
        self.base_url = f"http://127.0.0.1:{self.port}"

        self._migrate()
        self._seed()
        self._serve()
        self._wait_ready()
        return self

    def _migrate(self) -> None:
        """``alembic upgrade head`` against the TEMP database (DATABASE_URL passed explicitly
        — without it alembic would resolve to the real ``backend/app.db``)."""
        env = dict(os.environ)
        env["DATABASE_URL"] = self.database_url
        result = subprocess.run(
            [self.python, "-m", "alembic", "upgrade", "head"],
            cwd=str(REPO_ROOT), env=env, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            raise RuntimeError(f"alembic upgrade head failed: {result.stderr[-800:]}")

    def _seed(self) -> None:
        env = self._child_env()
        env["PYTHONPATH"] = str(BACKEND_ROOT)
        snippet = (
            "import json, e2e_seed; from database import SessionLocal, engine, Base;"
            # the SAME bootstrap order main.py uses at import: ORM create_all, then the
            # additive ensure_* passes (create_all cannot add a column, ensure_* can).
            "import models, usage.models, data_plane.models, learning.wrong_answers.models;"
            "from database_schema import ensure_database_schema;"
            "Base.metadata.create_all(bind=engine); ensure_database_schema(engine);"
            "db = SessionLocal();"
            f"identity = e2e_seed.seed(db, username={self.username!r},"
            f" password={self.password!r}, tier={self.tier!r});"
            "identity.update(e2e_seed.record_course_wrong_answer(db,"
            f" username={self.username!r}));"
            "print(json.dumps(identity, ensure_ascii=False)); db.close()"
        )
        result = subprocess.run(
            [self.python, "-c", snippet], cwd=str(BACKEND_ROOT / "scripts"), env=env,
            capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            raise RuntimeError(f"seed failed: {result.stderr[-800:]}")
        self.seed_identity = json.loads(result.stdout.strip().splitlines()[-1])

    def _serve(self) -> None:
        self.heartbeat_path = Path(self.temp_dir) / "heartbeat"
        self._touch_heartbeat()
        self._start_heartbeat()
        self._log_handle = open(self.log_path, "a", encoding="utf-8")
        self.process = subprocess.Popen(
            [self.python, str(BACKEND_ROOT / "scripts" / "e2e_serve.py"),
             "--host", "127.0.0.1", "--port", str(self.port),
             "--heartbeat", str(self.heartbeat_path)],
            cwd=str(BACKEND_ROOT), env=self._child_env(),
            stdout=self._log_handle, stderr=subprocess.STDOUT)

    def _touch_heartbeat(self) -> None:
        if self.heartbeat_path is None:
            return
        try:
            self.heartbeat_path.write_text(str(time.time()), encoding="utf-8")
        except OSError:
            pass

    def _start_heartbeat(self) -> None:
        """Keep the child's watchdog alive. If THIS process dies without cleaning up — killed
        with an uncatchable signal, a crashed test runner — the child notices the silence and
        exits on its own instead of serving an orphaned backend forever."""
        self._heartbeat_stop.clear()

        def _beat() -> None:
            while not self._heartbeat_stop.wait(1.0):
                self._touch_heartbeat()

        self._heartbeat_thread = threading.Thread(target=_beat, daemon=True,
                                                  name="e2e-harness-heartbeat")
        self._heartbeat_thread.start()

    def _wait_ready(self) -> None:
        if _wait_for_health(self.base_url, self.process):
            return
        tail = ""
        if self.log_path and self.log_path.exists():
            tail = self.log_path.read_text(encoding="utf-8", errors="replace")[-1500:]
        self.stop()
        raise RuntimeError(f"backend never became healthy at {self.base_url}\n{tail}")

    def stop(self) -> None:
        """Deterministic shutdown: only OUR process, then OUR temp directory."""
        self._heartbeat_stop.set()
        if self._heartbeat_thread is not None:
            self._heartbeat_thread.join(timeout=3)
            self._heartbeat_thread = None
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=10)
        self.process = None
        if self._log_handle is not None:
            # Windows refuses to delete a directory that still has an open handle in it.
            self._log_handle.close()
            self._log_handle = None
        if self.temp_dir is not None and not self.keep:
            self._remove_temp_dir(self.temp_dir)
        self.temp_dir = None

    @staticmethod
    def _remove_temp_dir(path: Path) -> None:
        """Delete the temp directory, with a short retry for Windows handle release."""
        for attempt in range(5):
            shutil.rmtree(path, ignore_errors=True)
            if not path.exists():
                return
            time.sleep(0.3 * (attempt + 1))
        shutil.rmtree(path, ignore_errors=True)

    # ---- contracts ----

    def bootstrap(self) -> dict:
        """The stable contract a consumer (Playwright / Codex) may depend on."""
        return {
            "base_url": self.base_url,
            "port": self.port,
            "health": f"{self.base_url}/api/health",
            "username": self.username,
            "password": self.password,
            "tier": self.tier,
            "course_id": self.seed_identity.get("course_id"),
            "exam_module_id": self.seed_identity.get("exam_module_id"),
            "exercise_id": self.seed_identity.get("exercise_id"),
            "login_path": "/login",
            "auth": "session cookie (ai_session); POST /login {username, password}",
            "data_origin": self.data_origin,
            "app_env": self.app_env,
            "database_url": self.database_url,
            "temp_dir": str(self.temp_dir),
            "log": str(self.log_path),
            "frontend": {
                "vite_api_base_url": self.base_url,
                "note": ("run the dev server on 127.0.0.1:5173 and set VITE_API_BASE_URL to "
                         "base_url — both 127.0.0.1, so the SameSite=Lax session cookie is "
                         "sent; no frontend source change is needed"),
            },
            "cleanup": "SIGINT/SIGTERM (or stop()) terminates only this backend and removes "
                       "the temp directory",
        }

    # ---- context manager ----

    def __enter__(self) -> "E2EEnvironment":
        return self.start()

    def __exit__(self, *_exc) -> None:
        self.stop()


def main() -> int:
    parser = argparse.ArgumentParser(description="Start the isolated authenticated E2E backend")
    parser.add_argument("--port", type=int, default=0, help="0 = pick a free port")
    parser.add_argument("--username", default=DEFAULT_USERNAME)
    parser.add_argument("--password", default=DEFAULT_PASSWORD)
    parser.add_argument("--tier", default="standard", choices=("free", "standard", "advanced"))
    parser.add_argument("--data-origin", default="ACCEPTANCE", choices=("ACCEPTANCE", "TEST"))
    parser.add_argument("--json", action="store_true", help="print the bootstrap contract")
    parser.add_argument("--keep", action="store_true", help="keep the temp dir on shutdown")
    args = parser.parse_args()

    env = E2EEnvironment(username=args.username, password=args.password, tier=args.tier,
                        port=args.port, data_origin=args.data_origin, keep=args.keep)

    def _shutdown(_signum=None, _frame=None):
        env.stop()
        raise SystemExit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    try:
        env.start()
    except Exception as exc:  # noqa: BLE001 — the harness reports, it does not retry
        print(f"E2E harness failed: {exc}", file=sys.stderr)
        return 1

    contract = env.bootstrap()
    if args.json:
        print(json.dumps(contract, ensure_ascii=False), flush=True)
    else:
        for key, value in contract.items():
            print(f"{key}: {value}")
    print("READY — press Ctrl+C to stop", file=sys.stderr, flush=True)

    try:
        while env.process is not None and env.process.poll() is None:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        env.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
