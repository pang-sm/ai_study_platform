"""Programming Debug Agent — ONE bounded, multi-step repair workflow.

WORKBENCH ≠ AGENT
-----------------
``POST /code/analyze`` and ``POST /code/diagnose`` stay exactly as they are: one question,
one answer. This module adds the thing they never were — a **bounded loop** that diagnoses a
failing submission, proposes a patch, RUNS the exercise's own tests through the existing
execution backend, inspects the result and optionally repairs once more.

HARD BOUNDS (the whole point of the feature)
--------------------------------------------
    MAX_ITERATIONS     model repair cycles            (never an open loop)
    MAX_EXECUTIONS     real test runs                 (tests-before + one per repair)
    MAX_MODEL_STEPS    hard cap on model invocations
    MAX_WALL_CLOCK_S   the agent stops STARTING steps after this budget

Every bound is checked BEFORE a step starts, so a step already in flight can never push the
workflow past a bound. Per-execution timeouts stay exactly where they are — the existing
runner's — because this module must not change execution semantics (§P3A).

NO SECOND AI SYSTEM
-------------------
Every model step goes through ``execute_programming_ai`` → ``ai.orchestrator`` with capability
``programming.agent``: the same Subscription → Capability Permission → Usage reserve → Router
→ Gateway → settle path as every other product AI call. One model step = one ``ai_requests``
row with a DETERMINISTIC ``request_id`` derived from the run id, so the whole workflow's cost
and latency are auditable per step.

WHAT IS DURABLE
---------------
* each model step → its own ``ai_requests`` row (request_id, capability, status, credits,
  provider/model, started_at → finished_at = latency, terminal state);
* each execution step → recorded in this run's trace (tests result, duration);
* the run → canonical ``programming_agent_started`` / ``programming_agent_completed`` /
  ``programming_agent_failed`` events whose payload carries the bounded per-step trace
  (index, action, status, latency, tests result, ai_request_id, credits, bounded patch).

The learner's own files are NEVER modified: the agent repairs a working COPY. A run is
advisory — it proposes; the learner decides what to save.
"""
from __future__ import annotations

import difflib
import json
import logging
import time
import uuid

from sqlalchemy.orm import Session as DbSession

from .ai import execute_programming_ai
from .context import build_programming_context

logger = logging.getLogger("learning.spaces.programming")

CAPABILITY = "programming.agent"

# ---- bounds (CONFIG; the workflow is unrepresentable without them) ----
MAX_ITERATIONS = 3
MAX_EXECUTIONS = 4
MAX_MODEL_STEPS = 7                     # diagnose+patch per cycle (3×2) + the explanation
MAX_WALL_CLOCK_SECONDS = 240

# ---- content bounds ----
MAX_CODE_CHARS = 20_000
MAX_CONTENT_CHARS = 12_000
MAX_DIFF_CHARS = 6_000
MAX_DIFF_LINES = 60

# ---- step vocabulary (closed set; the trace is a template, not free text) ----
ACTION_TESTS_BEFORE = "tests_before"
ACTION_DIAGNOSE = "diagnose"
ACTION_PROPOSE_PATCH = "propose_patch"
ACTION_RUN_TESTS = "run_tests"
ACTION_EXPLAIN = "explain"

STATUS_OK = "ok"
STATUS_FAILED = "failed"
STATUS_SKIPPED = "skipped"

RUN_COMPLETED = "completed"
RUN_FAILED = "failed"
RUN_NO_REPAIR_NEEDED = "no_repair_needed"

TESTS_ALREADY_PASSING = "tests_already_passing"


class AgentRefusal(Exception):
    """The workflow cannot run as asked — a caller-facing 4xx reason, not a crash."""

    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason
        self.message = message


# ---------------------------------------------------------------- helpers

def _bounded(text, limit: int) -> str:
    value = str(text or "")
    return value if len(value) <= limit else value[:limit]


def diff_summary(before: str, after: str) -> str:
    """A compact unified diff for the TRACE. A readable record, not a patch format."""
    lines = list(difflib.unified_diff((before or "").splitlines(),
                                      (after or "").splitlines(),
                                      lineterm="", n=2))
    body = [line for line in lines if not line.startswith(("---", "+++"))]
    return _bounded("\n".join(body[:MAX_DIFF_LINES]), MAX_DIFF_CHARS)


def _extract_json_object(text: str) -> dict | None:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        return None
    try:
        data = json.loads(text[start:end + 1])
    except (TypeError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _safe_filename(name, allowed: set[str]) -> str | None:
    """The model may only ever name a file that is ALREADY part of this run.

    A path is never joined, normalized or resolved: the name must match one of the caller's
    own working files exactly, or be the UNAMBIGUOUS basename of exactly one of them. That is
    what makes "no cross-project file access" a property of the code rather than a promise.
    """
    text = str(name or "").strip()
    if not text or "/" in text or "\\" in text or ".." in text:
        return None
    if text in allowed:
        return text
    matches = [candidate for candidate in allowed
               if candidate.rsplit("/", 1)[-1] == text]
    return matches[0] if len(matches) == 1 else None


def _tests_view(result: dict) -> dict:
    """The compact, factual part of an execution result kept in the trace."""
    return {
        "status": result.get("status"),
        "passed": bool(result.get("passed")),
        "passed_count": result.get("passed_count"),
        "total_count": result.get("total_count"),
        "duration_ms": result.get("duration_ms"),
        "tests_executed": result.get("tests_executed"),
    }


def _files_text(files: list[dict], limit: int = MAX_CODE_CHARS) -> str:
    parts = []
    for item in files:
        parts.append(f"===== file: {item.get('filename')} =====\n{item.get('content') or ''}")
    return _bounded("\n\n".join(parts), limit)


def _failures_text(result: dict, limit: int = 2000) -> str:
    cases = result.get("cases") or []
    broken = [c for c in cases if c.get("status") not in ("passed",)]
    if broken:
        return _bounded("\n".join(
            f"- {c.get('name') or c.get('id')}: {c.get('status')} "
            f"{(c.get('reason') or '')[:160]}" for c in broken[:8]), limit)
    return _bounded(result.get("summary") or result.get("stderr")
                    or result.get("compile_error") or "", limit)


def _tests_phrase(view: dict | None) -> str:
    view = view or {}
    return f"{view.get('passed_count')}/{view.get('total_count')} ({view.get('status')})"


# ---------------------------------------------------------------- the execution seam

def execute_exercise_tests(db: DbSession, user, exercise, project, files: list[dict],
                           *, submission: bool = False) -> dict:
    """Run one exercise's tests through the EXISTING execution backend.

    The ONLY seam onto execution, and deliberately a thin one: the real runner
    (``main._run_official_exercise_tests``) decides languages, sandboxing, timeouts and which
    test bundle may run. Nothing here re-implements, re-orders or relaxes it — the working
    copy is passed in the runner's own file shape (``relative_path`` + ``content``).
    """
    from types import SimpleNamespace

    from main import _run_official_exercise_tests   # lazy: avoids an import cycle
    adapted = [SimpleNamespace(relative_path=f["filename"], filename=f["filename"],
                               content=f["content"]) for f in files]
    return _run_official_exercise_tests(project, exercise, adapted, submission=submission)


# ---------------------------------------------------------------- prompts
#
# Built here and passed as messages: no provider, model name or gateway detail appears in
# this module or in anything it returns.

_DIAGNOSE_PROMPT = """你是一名编程导师，正在帮助学生修复未通过的代码。

题目:{title}
语言:{language}
题目描述:{description}

学生当前代码:
{code}

测试失败信息:
{failures}

请诊断问题。严格返回JSON(不要markdown代码块):
{{"diagnosis":"问题根因(中文,150字内)","evidence":"来自测试输出的证据","fix_direction":"修复方向"}}"""

_PATCH_PROMPT = """你是一名编程导师。根据诊断结果,给出修复后的完整文件内容。

题目:{title}
语言:{language}
诊断:{diagnosis}
当前代码:
{code}

要求:
1. 保持原有编程风格和必要注释
2. 只修复问题,不要重写无关部分
3. 严格返回JSON(不要markdown代码块):
{{"file":"文件名","content":"修复后的完整文件内容","summary":"改动说明(中文,100字内)"}}"""

_EXPLAIN_PROMPT = """你是一名编程导师。请用中文向学生解释这次修复(200字内:原来错在哪、怎么修的、如何避免)。

题目:{title}
诊断:{diagnosis}
改动说明:{summary}
修复前测试:{before}
修复后测试:{after}

直接输出解释文字,不要JSON。"""


# ---------------------------------------------------------------- the workflow

def run_debug_agent(db: DbSession, user, *, exercise, project=None,
                    files: list[dict] | None = None) -> dict:
    """Run ONE bounded debug workflow over the caller's own exercise.

    ``files`` is the working copy the agent repairs — the caller's own project files, or
    their own submitted code. ``project`` is the caller's own CodeProject for this exercise
    when one exists (the execution backend needs it); it is never written to.
    """
    if exercise is None or not getattr(exercise, "is_active", False) or \
            getattr(exercise, "quality_status", None) != "approved":
        raise AgentRefusal("exercise_not_found", "题目不存在或未上架")

    working = [{"filename": f.get("filename"), "content": str(f.get("content") or "")}
               for f in (files or []) if f.get("filename")]
    if not working:
        raise AgentRefusal("no_working_code", "没有可修复的代码")
    allowed_files = {f["filename"] for f in working}

    # Entitlement is checked BEFORE the baseline test run: a tier that cannot use the agent
    # should not have its code executed on the way to a refusal. The orchestrator gates again
    # on every step — this is the same policy module, used early, not a second policy.
    from fastapi import HTTPException
    from ops import feature_flags
    from usage import service as usage_service
    if not feature_flags.capability_permitted(
            db, user.id, usage_service.effective_subscription(db, user.id),
            CAPABILITY)["allowed"]:
        raise HTTPException(status_code=403, detail="AI capability unavailable")

    language = getattr(exercise, "language", None) or ""
    context = build_programming_context(user, language=language, exercise_id=exercise.id)
    if context.user_id != getattr(user, "id", None):
        raise AgentRefusal("context_mismatch", "学习上下文不属于当前用户")

    run_id = uuid.uuid4().hex
    started_at = time.monotonic()
    steps: list[dict] = []
    model_steps = 0
    executions = 0

    def _within_budget() -> bool:
        return ((time.monotonic() - started_at) < MAX_WALL_CLOCK_SECONDS
                and model_steps < MAX_MODEL_STEPS and executions < MAX_EXECUTIONS)

    def _ai_step(action: str, messages: list[dict], *, temperature: float = 0.2,
                 max_tokens: int = 900) -> tuple[str, dict]:
        """ONE model step: its own deterministic request_id, reservation and settlement.

        Returns ``(content, step)`` where ``step`` IS the row in the trace — the caller
        annotates that same dict with what the step produced (a file, a patch), so the trace
        and the response can never describe different things.
        """
        nonlocal model_steps
        request_id = f"{run_id}:{len(steps)}:{action}"
        step = {"step_index": len(steps), "action": action, "status": STATUS_OK,
                "ai_request_id": request_id, "capability": CAPABILITY,
                "latency_ms": None, "credits": None, "estimated_credits": None}
        steps.append(step)
        step_started = time.monotonic()
        try:
            result = execute_programming_ai(
                db, user, CAPABILITY, messages, learning_context=context,
                request_id=request_id, temperature=temperature, max_tokens=max_tokens)
        except Exception:
            # A step that failed is still a step: it keeps its identity and its latency.
            step["status"] = STATUS_FAILED
            step["latency_ms"] = int((time.monotonic() - step_started) * 1000)
            raise
        model_steps += 1
        step["latency_ms"] = int((time.monotonic() - step_started) * 1000)
        step["credits"] = result.actual_credits
        step["estimated_credits"] = result.estimated_credits
        return result.content or "", step

    def _execution_step(action: str, candidate: list[dict]) -> dict:
        nonlocal executions
        step = {"step_index": len(steps), "action": action, "status": STATUS_OK,
                "latency_ms": None, "tests": None}
        steps.append(step)
        step_started = time.monotonic()
        try:
            result = execute_exercise_tests(db, user, exercise, project, candidate)
        except Exception:
            step["status"] = STATUS_FAILED
            step["latency_ms"] = int((time.monotonic() - step_started) * 1000)
            raise
        executions += 1
        view = _tests_view(result)
        step["latency_ms"] = int((time.monotonic() - step_started) * 1000)
        step["status"] = STATUS_OK if view["passed"] else STATUS_FAILED
        step["tests"] = view
        return {"result": result, "view": view, "step": step}

    _emit_started(user, run_id, exercise, language)

    try:
        # 1. BASELINE: does the submitted code actually fail?
        before = _execution_step(ACTION_TESTS_BEFORE, working)
        tests_before = before["view"]
        if tests_before["passed"]:
            # Nothing to repair. Saying so is the honest answer: inventing a fix for a
            # passing submission would fabricate a defect the learner never had.
            return _finish(db, user, run_id, RUN_NO_REPAIR_NEEDED, steps, working, exercise,
                           language=language, tests_before=tests_before,
                           reason=TESTS_ALREADY_PASSING)

        current = working
        final_view = tests_before
        last_diagnosis = ""
        last_summary = ""
        stop_reason = "max_iterations"

        for _cycle in range(MAX_ITERATIONS):
            if not _within_budget():
                stop_reason = "budget_exhausted"
                break
            # 2. diagnose
            diagnosis_text, _diagnosis_step = _ai_step(ACTION_DIAGNOSE, [{"role": "user",
                "content": _DIAGNOSE_PROMPT.format(
                    title=exercise.title, language=language,
                    description=_bounded(exercise.description, 1200),
                    code=_files_text(current),
                    failures=_failures_text(before["result"]))}])
            diagnosis = _extract_json_object(diagnosis_text) or {}
            last_diagnosis = _bounded(diagnosis.get("diagnosis") or diagnosis_text, 800)

            if not _within_budget():
                stop_reason = "budget_exhausted"
                break
            # 3. propose a patch — ADVISORY: applied to the working copy only, never to the
            #    learner's stored files.
            patch_text, patch_step = _ai_step(ACTION_PROPOSE_PATCH, [{"role": "user",
                "content": _PATCH_PROMPT.format(
                    title=exercise.title, language=language,
                    diagnosis=last_diagnosis, code=_files_text(current))}])
            patch = _extract_json_object(patch_text) or {}
            filename = _safe_filename(patch.get("file"), allowed_files)
            new_content = patch.get("content")
            if filename is None or not isinstance(new_content, str) or not new_content.strip():
                patch_step["status"] = STATUS_FAILED
                patch_step["reason"] = "unusable_patch"
                stop_reason = "patch_not_applicable"
                break
            new_content = _bounded(new_content, MAX_CONTENT_CHARS)

            previous = next((f["content"] for f in current
                             if f["filename"] == filename), "")
            patch_step["file"] = filename
            patch_step["patch"] = diff_summary(previous, new_content)
            last_summary = _bounded(patch.get("summary") or "", 300)
            current = [{**f, "content": new_content if f["filename"] == filename
                        else f["content"]} for f in current]

            if not _within_budget():
                stop_reason = "budget_exhausted"
                break
            # 4. run the exercise's own tests against the patched copy
            after = _execution_step(ACTION_RUN_TESTS, current)
            final_view = after["view"]
            if final_view["passed"]:
                stop_reason = "tests_passed"
                break
            before = after          # the next cycle diagnoses the NEW failure output

        # 5. the final explanation — a model step, so it is bounded and billed like the rest
        explanation = ""
        if _within_budget():
            explain_text, _explain_step = _ai_step(ACTION_EXPLAIN, [{"role": "user",
                "content": _EXPLAIN_PROMPT.format(
                    title=exercise.title, diagnosis=last_diagnosis or "（未产出诊断）",
                    summary=last_summary, before=_tests_phrase(tests_before),
                    after=_tests_phrase(final_view))}], max_tokens=500)
            explanation = _bounded(explain_text, 2000)
        else:
            steps.append({"step_index": len(steps), "action": ACTION_EXPLAIN,
                          "status": STATUS_SKIPPED, "reason": stop_reason})

        status = RUN_COMPLETED if final_view["passed"] else RUN_FAILED
        return _finish(db, user, run_id, status, steps, current, exercise,
                       language=language, tests_before=tests_before, tests_after=final_view,
                       explanation=explanation, stop_reason=stop_reason,
                       diagnosis=last_diagnosis, summary=last_summary)
    except Exception as exc:  # noqa: BLE001 — a failed workflow is a FACT, not a lost run
        error_category = _error_category_of(exc)
        logger.warning("programming.agent_failed run_id=%s error=%s",
                       run_id, type(exc).__name__)
        _emit_failed(user, run_id, error_category, steps, language=language)
        if not model_steps and executions == 0:
            # Nothing was consumed and nothing was produced: the caller gets the REAL refusal
            # (403 tier / 429 budget / 502 technical) instead of a 200 that hides it.
            raise
        return {
            "agent_run_id": run_id,
            "status": RUN_FAILED,
            "error_category": error_category,
            "exercise_id": getattr(exercise, "id", None),
            "language": language,
            "steps": steps,
            "iterations_used": _iterations_used(steps),
            "executions_used": executions,
            "tests_before": None,
            "tests_after": None,
            "proposed_patch": None,
            "final_code": None,
            "explanation": "",
            "usage": _usage_summary(steps),
            "message": f"工作流在第 {len(steps)} 步中止",
        }


def _error_category_of(exc: Exception) -> str:
    status_code = getattr(exc, "status_code", None)
    if isinstance(status_code, int):
        return f"http_{status_code}"
    return type(exc).__name__


def _iterations_used(steps: list[dict]) -> int:
    return sum(1 for s in steps if s["action"] == ACTION_PROPOSE_PATCH)


def _patch_metrics(diff_text: str) -> dict:
    """What the patch DID, as numbers — never the patch text.

    The canonical event stream must not carry source code (learning.records.envelope §34), so
    a step records its patch by size and shape; the diff itself travels in the response and in
    the model step's own audit row.
    """
    lines = (diff_text or "").splitlines()
    return {
        "patch_chars": len(diff_text or ""),
        "lines_added": sum(1 for line in lines if line.startswith("+")),
        "lines_removed": sum(1 for line in lines if line.startswith("-")),
    }


def step_trace(steps: list[dict]) -> list[dict]:
    """The code-free per-step record that may enter a canonical event payload.

    One entry per step: its index, action, status, latency, cost, the id of the AI request
    that served it, the exercise's own test result, and — for a patch — its SIZE. No source
    code, no diff, no prompt and no model response: those live in their own stores.
    """
    trace = []
    for step in steps:
        entry = {
            "index": step.get("step_index"),
            "action": step.get("action"),
            "status": step.get("status"),
            "latency_ms": step.get("latency_ms"),
            "credits": step.get("credits"),
            "ai_request_id": step.get("ai_request_id"),
        }
        if step.get("tests"):
            entry["tests"] = step["tests"]
        if step.get("file"):
            entry["file"] = step["file"]
        if step.get("patch"):
            entry["patch"] = _patch_metrics(step["patch"])
        if step.get("reason"):
            entry["reason"] = step["reason"]
        trace.append({key: value for key, value in entry.items() if value is not None})
    return trace


def _usage_summary(steps: list[dict]) -> dict:
    credits = [s["credits"] for s in steps if s.get("credits") is not None]
    estimated = [s["estimated_credits"] for s in steps
                 if s.get("estimated_credits") is not None]
    return {
        "model_steps": sum(1 for s in steps if s["action"] in
                           (ACTION_DIAGNOSE, ACTION_PROPOSE_PATCH, ACTION_EXPLAIN)),
        "execution_steps": sum(1 for s in steps if s.get("tests")),
        "actual_credits": sum(credits) if credits else 0,
        "estimated_credits": sum(estimated) if estimated else 0,
    }


def _finish(db, user, run_id, status, steps, final_files, exercise, *, language,
            tests_before=None, tests_after=None, explanation="", stop_reason="",
            diagnosis="", summary="", reason=None) -> dict:
    patch_step = next((s for s in steps if s["action"] == ACTION_PROPOSE_PATCH
                       and s.get("patch")), None)
    final_code = None
    if patch_step is not None:
        final_code = next((f["content"] for f in final_files
                           if f["filename"] == patch_step["file"]), None)
    _emit_completed(user, run_id, status, steps, language=language,
                    tests_before=tests_before, tests_after=tests_after, reason=reason)
    return {
        "agent_run_id": run_id,
        "status": status,
        "reason": reason,
        "stop_reason": stop_reason,
        "exercise_id": getattr(exercise, "id", None),
        "language": language,
        "steps": steps,
        "iterations_used": _iterations_used(steps),
        "executions_used": sum(1 for s in steps if s.get("tests")),
        "tests_before": tests_before,
        "tests_after": tests_after,
        "proposed_patch": patch_step.get("patch") if patch_step else None,
        "patch_file": patch_step.get("file") if patch_step else None,
        "final_code": final_code,
        "diagnosis": diagnosis,
        "patch_summary": summary,
        "explanation": explanation,
        "usage": _usage_summary(steps),
    }


# ---------------------------------------------------------------- events
#
# ONE producer for these three families (learning/records/taxonomy.py). Emission is
# failure-isolated on the producers' own side: a records problem never fails a workflow
# whose facts already committed.

def _emit_started(user, run_id, exercise, language) -> None:
    try:
        from learning.records import producers
        producers.emit_programming_agent_started(
            user_id=user.id, agent_run_id=run_id,
            exercise_id=getattr(exercise, "id", None), language=language,
            max_iterations=MAX_ITERATIONS, max_executions=MAX_EXECUTIONS,
            occurred_at=None, source_user_ref=getattr(user, "username", None))
    except Exception as exc:  # noqa: BLE001
        logger.warning("programming.agent_started_event_failed error=%s", type(exc).__name__)


def _emit_completed(user, run_id, status, steps, *, language, tests_before, tests_after,
                    reason) -> None:
    try:
        from learning.records import producers
        producers.emit_programming_agent_completed(
            user_id=user.id, agent_run_id=run_id, status=status, language=language,
            steps=step_trace(steps), tests_before=tests_before, tests_after=tests_after,
            reason=reason, occurred_at=None,
            source_user_ref=getattr(user, "username", None))
    except Exception as exc:  # noqa: BLE001
        logger.warning("programming.agent_completed_event_failed error=%s", type(exc).__name__)


def _emit_failed(user, run_id, error_category, steps, *, language) -> None:
    try:
        from learning.records import producers
        producers.emit_programming_agent_failed(
            user_id=user.id, agent_run_id=run_id, error_category=error_category,
            language=language, steps=step_trace(steps), occurred_at=None,
            source_user_ref=getattr(user, "username", None))
    except Exception as exc:  # noqa: BLE001
        logger.warning("programming.agent_failed_event_failed error=%s", type(exc).__name__)
