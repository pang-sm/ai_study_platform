"""P6.1 E2E server entry — THE product app, with only the provider boundary faked.

WHAT THIS IS
------------
The E2E harness needs a real HTTP backend. It must be the SAME app the product runs
(``main:app``), not a second one, and every AI call must still travel the real chain:

    Capability → Permission → Usage reserve → Router → Provider (FAKE) → settle → ai_requests

Only the last hop is substituted: ``ai.orchestrator.default_provider_factory`` is replaced with
a factory that returns the existing ``FakeProvider``. Nothing else is patched — no HTTP
mocking, no stubbed orchestrator — so a ``request_id`` produced here is a real ``ai_requests``
identity and ``POST /ai/feedback`` works against it exactly as in production.

WHY IT IS A TEST-INFRA FILE AND NOT A PRODUCT FLAG
--------------------------------------------------
A production environment variable that swaps the model provider would be a security hole
(one env var away from a deployment that silently answers from a canned string). The patch
lives in this launcher, which is only ever executed by the harness and never imported by
``main``.

ISOLATION IS THE CALLER'S JOB
-----------------------------
This file starts whatever database ``DATABASE_URL`` names. It never defaults that value: an
absent ``DATABASE_URL`` is refused here, so this process can never fall back to
``backend/app.db``.

USAGE (the harness calls it; a human normally should not)
    DATABASE_URL=sqlite:////tmp/x.db python scripts/e2e_serve.py --port 8123
"""
from __future__ import annotations

import argparse
import os
import sys
import threading
import time
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

# The harness touches this file once a second. If it goes quiet the harness is gone — killed,
# crashed, or closed — and this process must not keep serving an orphaned backend on a port
# nobody owns any more. The FILE is the signal because it is the one mechanism that works the
# same way when the parent dies without a chance to clean up.
HEARTBEAT_STALE_SECONDS = 20


def _start_heartbeat_watchdog(path: str | None) -> None:
    if not path:
        return
    heartbeat = Path(path)

    def _watch() -> None:
        while True:
            time.sleep(2)
            try:
                age = time.time() - heartbeat.stat().st_mtime
            except OSError:
                age = HEARTBEAT_STALE_SECONDS + 1
            if age > HEARTBEAT_STALE_SECONDS:
                print("E2E heartbeat lost — shutting down", file=sys.stderr, flush=True)
                os._exit(0)

    threading.Thread(target=_watch, daemon=True, name="e2e-heartbeat").start()


def fake_provider_factory(name: str):
    """The one substitution: any pool provider name → the shared FakeProvider double."""
    from ai.providers import FakeProvider
    return FakeProvider(provider=name or "fake", input_tokens=64, output_tokens=96)


def main() -> int:
    parser = argparse.ArgumentParser(description="E2E backend (fake provider, temp DB)")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--log-level", default="warning")
    parser.add_argument("--heartbeat", default="", help="file the harness keeps fresh")
    args = parser.parse_args()

    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url or "app.db" in database_url:
        print("REFUSED: DATABASE_URL must name an isolated database (never app.db)",
              file=sys.stderr)
        return 2

    _start_heartbeat_watchdog(args.heartbeat or None)

    from ai import orchestrator
    orchestrator.default_provider_factory = fake_provider_factory

    import uvicorn
    uvicorn.run("main:app", host=args.host, port=args.port, log_level=args.log_level)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
