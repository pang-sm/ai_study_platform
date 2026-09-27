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
import datetime
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


def _plan_adjustment_content(spec) -> str | None:
    """A plan proposal built from the REAL plan the backend just sent to the model.

    The stock double answers everything with one canned sentence, which is fine for chat and
    explanation ("did the request reach the model boundary?") and useless for a workflow whose
    answer is a STRUCTURED DIFF: the route parses JSON out of the model's reply, so a
    sentence-shaped reply is refused as ``unusable_proposal`` and the preview can never show
    the flow it is meant to show.

    What this returns is NOT a canned proposal. It reads the learner's own plan out of the
    prompt — `build_plan_adjustment_messages` puts that JSON in the user turn verbatim — and
    answers about those real tasks: a real `task_id` from that plan, and the learner's own goal
    text when they typed one. Nothing about a learner's plan is invented here, and every change
    still has to survive the route's own `_clean_changes` validation (unknown ids are dropped)
    before the learner ever sees it. The plan is not written: the proposal still needs the
    learner's explicit apply.

    Only the plan-adjustment system prompt is answered this way. Every other capability keeps
    the stock behaviour exactly, so nothing that already worked changes shape.
    """
    import json

    from prompts import PLAN_ADJUSTMENT_MARKER

    if not any(PLAN_ADJUSTMENT_MARKER in (message.content or "")
               for message in spec.messages):
        return None

    payload = None
    for message in spec.messages:
        text = message.content or ""
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end <= start:
            continue
        try:
            candidate = json.loads(text[start:end + 1])
        except ValueError:
            continue
        if isinstance(candidate, dict) and isinstance(candidate.get("plan"), dict):
            payload = candidate
    if payload is None:
        return None

    plan = payload["plan"]
    tasks = [task for task in plan.get("tasks") or [] if isinstance(task, dict)]
    goal = ""
    for message in spec.messages:
        marker = "学生本次的目标/偏好："
        text = message.content or ""
        if marker in text:
            goal = text.split(marker, 1)[1].strip()
    due = (datetime.date.today() + datetime.timedelta(days=3)).isoformat()
    later = (datetime.date.today() + datetime.timedelta(days=7)).isoformat()

    changes = []
    open_tasks = [task for task in tasks if task.get("status") != "completed"]
    # Each open task the plan actually holds is rescheduled — real ids from the learner's own
    # plan, so every change still has to survive the route's validation on the way back. Several
    # of them (not just the first) is what lets browser acceptance exercise the "查看调整详情"
    # collapse with a proposal that is genuinely several changes long.
    for task in open_tasks:
        if (task.get("due_date") or "").strip() == due:
            # Already at the proposed date — a no-op the route drops. Skipping it here keeps a
            # second run of the same harness honest instead of proposing nothing.
            continue
        changes.append({"op": "update_task", "task_id": task.get("task_id"), "due_date": due})
        if len(changes) >= 6:
            break
    if goal:
        # `review` because it is a kind every space's plan can actually own and complete
        # (learning.spaces.plan_task_types). The harness must not invent a task kind the product
        # could never produce — an earlier revision asked for `practice`, which no space accepts.
        changes.append({"op": "create_task", "title": goal[:60], "task_type": "review",
                        "due_date": later})
    if not changes:
        # No tasks and no goal: there is honestly nothing to propose, and the route says so.
        return None
    # `changes` only. The route derives the headline, the reason and the impact from these and
    # from the learner's own records — a prose `reason` here would be ignored.
    return json.dumps({"changes": changes}, ensure_ascii=False)


class _HarnessProvider:
    """The stock FakeProvider, plus a structured answer for the workflows that need one.

    Everything except ``complete`` is the shared double, so usage, settlement and the failure
    matrix behave exactly as everywhere else in the suite.
    """

    def __init__(self, **kwargs):
        from ai.providers import FakeProvider

        self._inner = FakeProvider(**kwargs)

    def __getattr__(self, item):
        if item == "_inner":
            raise AttributeError(item)
        return getattr(self._inner, item)

    def complete(self, spec):
        import dataclasses

        response = self._inner.complete(spec)
        scripted = _plan_adjustment_content(spec)
        return dataclasses.replace(response, content=scripted) if scripted else response

    def stream(self, spec):
        return self._inner.stream(spec)


def fake_provider_factory(name: str):
    """The one substitution: any pool provider name → the shared FakeProvider double."""
    return _HarnessProvider(provider=name or "fake", input_tokens=64, output_tokens=96)


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
