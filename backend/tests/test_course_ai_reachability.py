"""STEP 7G-C2 reachability gate: Course production AI cannot reach a provider directly.

Static, executable audit over ``main.py``:

  * every ``call_deepseek`` callsite must sit in a function declared NON-COURSE below,
    with the reason it is not a Course production path;
  * every Course AI endpoint must reach the unified AI boundary.

The declaration is the point: adding a new direct provider call anywhere makes this
test fail until it is either migrated or explicitly classified, so "0 course direct
provider calls" stays a checked fact instead of a remembered one.
"""
import ast
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
MAIN_SOURCE = (BACKEND_DIR / "main.py").read_text(encoding="utf-8")

LEGACY_PROVIDER_FN = "call_deepseek"
# `_scoped_ai_content` (STEP7H1) dispatches to the space that owns the request, so it is
# a boundary entry point in its own right; `_exam_ai_content` is the exam side of it.
AI_BOUNDARY_FNS = ("_course_ai_content", "execute_course_ai",
                   "_scoped_ai_content", "_exam_ai_content")

# Every remaining direct-provider callsite, with the space that owns it. A function
# listed here must reach the call ONLY through a non-Course branch.
# STEP7H3: the exam branches of handle_material_upload / chat / structure_practice_paper_text
# / refine_question_analysis_with_ai / _repair_json_with_ai / _generate_plan_preview_core and
# generate_exam_ai_questions all moved to the exam boundary, so the direct client remains
# only on the PROGRAMMING and non-course-legacy branches.
NON_COURSE_DIRECT_CALLS = {
    "chat": "programming branch only; Course → material.qa|tutor.chat, Exam → exam_prep",
    "analyze_code": "programming branch only; Course maps to programming.explain",
    "generate_code_challenge": "programming",
    "submit_code_challenge": "programming",
    "explain_challenge_failure": "programming",
    "generate_challenge_tests": "programming",
    "generate_learning_diagnosis": "programming",
    "_repair_generated_challenge_with_ai": "programming challenge repair",
    "structure_practice_paper_text": "legacy path when no db/user context is available",
    "refine_question_analysis_with_ai": "non-course / non-exam service_key branch only",
    "_repair_json_with_ai": "non-course / non-exam service_key branch only",
}

# Course production AI surface → the capability it must request.
COURSE_AI_ENDPOINTS = {
    "chat": {"material.qa", "tutor.chat"},
    "analyze_code": {"programming.explain"},
    "ai_generate_learning_report": {"report.generate"},
    "generate_tasks_from_diagnosis": {"planning.generate"},
    "generate_course_learning_practice": {"question.generate"},
    "generate_knowledge_points_preview": {"knowledge.structure"},
    "generate_knowledge_path_from_materials": {"knowledge.structure"},
    "explain_practice_question": {"question.explain"},
    "request_feedback": {"question.explain"},
    "generate_questions": {"question.generate"},
    "generate_task_question_preview": {"planning.generate"},
    "recommend_material_knowledge_links": {"knowledge.structure"},
    "_analyze_knowledge_preview_impl": {"knowledge.structure"},
    "generate_report_preview": {"report.generate"},
}


class _Index:
    def __init__(self, source: str):
        self.tree = ast.parse(source)
        self.funcs = [(n.lineno, n.end_lineno, n.name) for n in ast.walk(self.tree)
                      if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        self.routes = {}
        for node in self.tree.body:
            if not isinstance(node, ast.FunctionDef):
                continue
            for deco in node.decorator_list:
                if isinstance(deco, ast.Call) and getattr(deco.func, "attr", "") in (
                        "get", "post", "put", "delete", "patch"):
                    self.routes[node.name] = f"{deco.func.attr.upper()} {deco.args[0].value}"
        self._parents: dict[int, ast.AST] = {}
        for parent in ast.walk(self.tree):
            for child in ast.iter_child_nodes(parent):
                self._parents[id(child)] = parent

    def enclosing(self, lineno: int) -> str:
        found = sorted([f for f in self.funcs if f[0] <= lineno <= f[1]],
                       key=lambda f: f[1] - f[0])
        return found[0][2] if found else ""

    def calls_in(self, func_name: str, callee: str) -> list[ast.Call]:
        bounds = [f for f in self.funcs if f[2] == func_name]
        return [n for n in ast.walk(self.tree)
                if isinstance(n, ast.Call)
                and (getattr(n.func, "id", None) == callee
                     or getattr(n.func, "attr", None) == callee)
                and any(b[0] <= n.lineno <= b[1] for b in bounds)]

    def guarding_conditions(self, node: ast.AST) -> list[tuple[str, bool]]:
        """`(rendered test, negated)` for each branch on the way down to `node`.

        Polarity matters: a direct provider call in the ``else`` of
        ``if service == "course_learning"`` is guarded by the NEGATION of that test.
        """
        out, current = [], node
        while current is not None:
            parent = self._parents.get(id(current))
            if isinstance(parent, (ast.If, ast.IfExp, ast.While)) and parent.test is not current:
                if any(current is s for s in parent.orelse):
                    out.append((ast.unparse(parent.test), True))
                elif any(current is s for s in parent.body):
                    out.append((ast.unparse(parent.test), False))
            current = parent
        return out


@pytest.fixture(scope="module")
def index():
    return _Index(MAIN_SOURCE)


def test_every_direct_provider_callsite_is_declared_non_course(index):
    found = {}
    for node in ast.walk(index.tree):
        if (isinstance(node, ast.Call)
                and getattr(node.func, "id", None) == LEGACY_PROVIDER_FN):
            found.setdefault(index.enclosing(node.lineno), []).append(node.lineno)

    undeclared = sorted(set(found) - set(NON_COURSE_DIRECT_CALLS))
    assert not undeclared, (
        "new direct provider callsite(s) — migrate to the orchestrator or classify "
        f"them here with the space that owns them: {undeclared}")

    stale = sorted(set(NON_COURSE_DIRECT_CALLS) - set(found))
    assert not stale, f"declared callsites no longer exist, drop them: {stale}"


# A direct call inside a Course-capable endpoint is legal ONLY behind a guard that
# proves the request belongs to another space.
NON_COURSE_GUARD_MARKERS = ("exam_11408", "11408", "programming", "service_key")


def _proves_non_course(guards):
    for text, negated in guards:
        if negated and "course_learning" in text:
            return True
        if not negated and any(marker in text for marker in NON_COURSE_GUARD_MARKERS):
            return True
    return False


def test_direct_calls_in_course_endpoints_are_guarded_by_another_space(index):
    for func_name in sorted(set(COURSE_AI_ENDPOINTS) & set(NON_COURSE_DIRECT_CALLS)):
        calls = index.calls_in(func_name, LEGACY_PROVIDER_FN)
        assert calls, f"{func_name} is declared non-course but has no direct call"
        for call in calls:
            guards = index.guarding_conditions(call)
            assert _proves_non_course(guards), (
                f"{func_name}:{call.lineno} reaches {LEGACY_PROVIDER_FN} without an "
                f"exam/programming guard (guards seen: {guards})")


def test_pure_course_endpoints_never_call_a_provider_directly(index):
    pure_course = set(COURSE_AI_ENDPOINTS) - set(NON_COURSE_DIRECT_CALLS)
    for func_name in sorted(pure_course):
        assert not index.calls_in(func_name, LEGACY_PROVIDER_FN), (
            f"{func_name} reached {LEGACY_PROVIDER_FN} directly")


def test_every_course_ai_endpoint_reaches_the_unified_boundary(index):
    for func_name in COURSE_AI_ENDPOINTS:
        reachable = any(index.calls_in(func_name, boundary)
                        for boundary in AI_BOUNDARY_FNS)
        assert reachable, f"{func_name} does not reach the AI orchestrator boundary"


def test_course_endpoints_request_only_course_capabilities(index):
    """A Course endpoint must request a capability the tier policy actually knows."""
    from ai.pool import CAPABILITY_QUALIFICATION_PROXIES
    from usage.capabilities import ALL_CAPABILITIES

    proxies = CAPABILITY_QUALIFICATION_PROXIES
    for func_name, capabilities in COURSE_AI_ENDPOINTS.items():
        for capability in capabilities:
            assert capability in ALL_CAPABILITIES, capability
            assert proxies.get(capability, capability) in ALL_CAPABILITIES, capability


def test_legacy_provider_client_is_confined_to_declared_modules():
    """Only provider adapters may construct a raw provider client."""
    allowed = {
        Path("ai/providers/deepseek.py"), Path("ai/providers/qwen.py"),
        Path("ai/providers/ark.py"), Path("ai/providers/moonshot.py"),
        Path("ai/providers/zhipu.py"), Path("ai/providers/minimax.py"),
        Path("ai/discovery.py"),            # account discovery tooling, not a request path
        Path("qwen_parser.py"),             # visual OCR infrastructure
        Path("exam_paper_parser.py"),       # exam_11408 parsing path
        Path("membership.py"),              # legacy onboarding plan recommendation (OTHER)
        Path("main.py"),                    # legacy client; see NON_COURSE_DIRECT_CALLS
    }
    offenders = []
    for path in BACKEND_DIR.rglob("*.py"):
        rel = path.relative_to(BACKEND_DIR)
        if rel.parts[0] in {"tests", ".venv", "__pycache__"} or rel in allowed:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "OpenAI(" in text or "chat.completions.create" in text:
            offenders.append(str(rel))
    assert not offenders, f"raw provider clients outside adapters: {offenders}"
