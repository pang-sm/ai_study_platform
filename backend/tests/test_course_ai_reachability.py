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
# P6.1: `*_ai_result` are the SAME invocations returning the whole orchestrator result
# (so an endpoint can hand the caller the real `ai_requests` identity it produced), and
# `execute_programming_ai` is the programming adapter — reached by /code/analyze once its
# programming branch stopped using the legacy client.
AI_BOUNDARY_FNS = ("_course_ai_content", "execute_course_ai",
                   "_scoped_ai_content", "_exam_ai_content",
                   "_course_ai_result", "_exam_ai_result", "execute_programming_ai")

# Every remaining direct-provider callsite, with the space that owns it. A function
# listed here must reach the call ONLY through a non-Course branch.
# STEP7H3: the exam branches of handle_material_upload / chat / structure_practice_paper_text
# / refine_question_analysis_with_ai / _repair_json_with_ai / _generate_plan_preview_core and
# generate_exam_ai_questions all moved to the exam boundary, so the direct client remains
# only on the PROGRAMMING and non-course-legacy branches.
#
# P6.2 §A/§B removed `chat` and `submit_code_challenge` from this list: both now run every
# one of their branches through the unified boundary (see CLOSED_ENDPOINTS), so the guard
# keeps them only in the STRICTER set that must never reach the legacy client at all.
# What remains below is the honest, still-open programming surface: these are real product
# endpoints with a real model call that has not been converged yet, and each one owes the
# same closure (capability → permission → usage → router → gateway → settle → ai_requests).
# SECURITY_S1C removed the five PROGRAMMING entries that used to be here
# (generate_code_challenge, explain_challenge_failure, generate_challenge_tests,
# generate_learning_diagnosis, _repair_generated_challenge_with_ai). They now run through the
# unified boundary like every other programming AI call — capability permission, budget
# reservation, router, ledger — so they belong in the STRICTER set that must never reach the
# legacy client, not in this one. Removing them here is what makes the guard enforce that:
# a direct call reappearing in any of them fails this file.
NON_COURSE_DIRECT_CALLS = {
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


def test_main_py_builds_exactly_one_raw_provider_client():
    """A SECOND raw client in main.py is how the membership-recommendation bypass appeared.

    One client is the legacy ``call_deepseek`` client, whose three remaining callers are
    declared in ``NON_COURSE_DIRECT_CALLS`` and unreachable from a request. The function-level
    declaration list cannot see a new client, because it tracks ``call_deepseek`` calls — who
    *built* a client is invisible to it. SECURITY_S1C removed the second one
    (`/membership/recommendation` built its own client for an AI fallback layer); this asserts
    it does not come back.
    """
    constructions = [
        node for node in ast.walk(ast.parse(MAIN_SOURCE))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name) and node.func.id == "OpenAI"
    ]
    assert len(constructions) == 1, (
        "main.py must build exactly one raw provider client (the legacy call_deepseek client); "
        f"found {len(constructions)} at lines {[n.lineno for n in constructions]}")


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


# The ONE boundary allowed to construct or call a raw provider client: the provider
# infrastructure package. Its adapters own their SDK clients, and they share ``common.py``
# for the streaming driver — a helper that RECEIVES a client is part of the same layer, so the
# rule is expressed as a package rather than as a list of adapter filenames (a hand-written
# file list silently rejects a new module in an already-permitted layer).
PROVIDER_INFRASTRUCTURE_PACKAGE = ("ai", "providers")

# Constructing a raw client and CALLING one are different operations — only the first creates
# a client; the second borrows one it was handed. Both are forbidden outside the boundary,
# because business code that was handed a raw client bypasses the unified AI boundary exactly
# as effectively as business code that builds one. They are reported separately so the
# failure says which happened.
RAW_CLIENT_CONSTRUCTION_PATTERNS = ("OpenAI(", "AsyncOpenAI(")
RAW_CLIENT_CALL_PATTERNS = ("chat.completions.create",)

# Files with their own, already-reviewed reason to touch a provider outside that package.
# Deliberately NOT extended: a new entry would need the same kind of justification as these.
RAW_CLIENT_ALLOWED_FILES = (
    Path("ai/discovery.py"),            # account discovery tooling, not a request path
    Path("qwen_parser.py"),             # visual OCR infrastructure
    Path("exam_paper_parser.py"),       # exam_11408 parsing path
    Path("membership.py"),              # legacy onboarding plan recommendation (OTHER)
    Path("main.py"),                    # legacy client; see NON_COURSE_DIRECT_CALLS
)


def _raw_provider_offenders(sources: dict[Path, str]) -> dict[str, str]:
    """``{relative path: "constructs" | "calls"}`` for every raw provider use outside the boundary.

    A pure function of ``{relative path: source}``: the caller decides what to read, so the rule
    is exercised against the real tree and against synthetic sources by the same code.
    """
    offenders: dict[str, str] = {}
    for rel, text in sources.items():
        if rel.parts[0] in {"tests", ".venv", "__pycache__"}:
            continue
        if rel.parts[:2] == PROVIDER_INFRASTRUCTURE_PACKAGE or rel in RAW_CLIENT_ALLOWED_FILES:
            continue
        if any(pattern in text for pattern in RAW_CLIENT_CONSTRUCTION_PATTERNS):
            offenders[rel.as_posix()] = "constructs"
        elif any(pattern in text for pattern in RAW_CLIENT_CALL_PATTERNS):
            offenders[rel.as_posix()] = "calls"
    return offenders


def test_legacy_provider_client_is_confined_to_declared_modules():
    """Only the provider infrastructure layer may construct or call a raw provider client.

    Business / domain / application code reaches a provider through the unified boundary
    (orchestrator → capability permission → router → reserve → adapter), never by holding an
    SDK client of its own.
    """
    sources = {path.relative_to(BACKEND_DIR): path.read_text(encoding="utf-8", errors="ignore")
               for path in BACKEND_DIR.rglob("*.py")}
    offenders = _raw_provider_offenders(sources)
    assert not offenders, f"raw provider clients outside the boundary: {offenders}"


def test_the_raw_provider_scanner_still_flags_business_layer_usage():
    """Negative coverage for the rule above.

    Exempting the provider package is only safe while the scanner still rejects the layer it
    is protecting. These are synthetic sources, so this cannot depend on the tree's contents.
    """
    sources = {
        Path("learning/practice/service.py"): "from openai import OpenAI\nc = OpenAI(api_key=k)\n",
        Path("routers/course_learning.py"): "r = client.chat.completions.create(model='m')\n",
        Path("ai/providers/common.py"): "stream = client.chat.completions.create(model='m')\n",
        Path("ai/providers/deepseek.py"): "self._client = OpenAI(api_key=key)\n",
        Path("ai/discovery.py"): "return OpenAI(api_key=key, base_url=url), spec\n",
        Path("tests/test_something.py"): "OpenAI(\n",
    }

    offenders = _raw_provider_offenders(sources)

    assert set(offenders) == {"learning/practice/service.py",
                             "routers/course_learning.py"}, offenders
    assert offenders["learning/practice/service.py"] == "constructs"
    assert offenders["routers/course_learning.py"] == "calls"
    # the provider layer and the declared exceptions stay permitted
    assert "ai/providers/common.py" not in offenders
    assert "ai/providers/deepseek.py" not in offenders
    assert "ai/discovery.py" not in offenders
    # and the tests tree is never scanned
    assert "tests/test_something.py" not in offenders


# ══════════════════════════════════════════════════════════════════════════════
# P6.2 §D — the CLOSED product AI paths
#
# A product path named here is claimed to be CLOSED, which means exactly two things, and
# both are executed below:
#
#   * it REACHES the unified AI boundary, and
#   * it cannot reach a provider on its own — not through the legacy ``call_deepseek``
#     client, not by constructing a raw provider client, not by importing one.
#
# The claim is per-path and executable, so "0 forbidden bypasses" stays a checked fact
# instead of a remembered one. Only the Gateway / Provider layer may talk to a provider.
#
# The list is the P6.1+P6.2 closure set — the three surfaces converged in those two rounds
# (`/chat`, `/code/analyze`, the challenge submit AI branch) plus the advanced workflows
# that were built on the boundary from the start (Deep Study, Report, Wrong Analysis,
# Plan Adjustment, Debug Agent). It is NOT "every programming endpoint": the programming
# endpoints that still call the legacy client are declared in NON_COURSE_DIRECT_CALLS
# above, and they stay visible there until each one is converged in its own round.
# ══════════════════════════════════════════════════════════════════════════════

# Endpoint handler → the boundary entry points it is allowed to use. At least one must be
# called; NONE of the provider markers below may appear anywhere in its body.
CLOSED_ENDPOINTS = {
    "chat": ("_course_ai_result", "_exam_ai_result", "execute_programming_ai"),
    "analyze_code": ("_course_ai_result", "execute_programming_ai"),
    "submit_code_challenge": ("execute_programming_ai",),
}

# Module → the product path it implements. Every closed module must use the orchestrator
# (directly or through its space's adapter) and reach no provider by itself.
CLOSED_MODULES = {
    Path("learning/deep_study.py"): "Deep Study (tutor.strong_reasoning)",
    Path("learning/report.py"): "Learning Report (report.generate)",
    Path("learning/wrong_analysis.py"): "Wrong Analysis (wrong_answer.analyze)",
    Path("learning/plan_adjustment.py"): "Plan Adjustment (planning.adjust)",
    Path("learning/spaces/programming/agent.py"): "Debug Agent (programming.agent)",
}

BOUNDARY_TOKENS = ("execute_course_ai", "execute_exam_ai", "execute_programming_ai",
                   "AIOrchestrator")
# Calls that mean "this code is talking to a provider itself".
FORBIDDEN_CALLS = ("call_deepseek", "OpenAI", "AsyncOpenAI")
FORBIDDEN_MODULES = ("openai", "ai.providers")


def _provider_violations(tree: ast.AST, within: tuple[int, int] | None = None) -> list[str]:
    """Provider reach in a parsed module, or inside one line range of it.

    Read from the AST rather than the text so a comment that merely NAMES the legacy client
    cannot make a clean path look dirty (nor a dirty one look clean).
    """
    out: list[str] = []
    for node in ast.walk(tree):
        if within is not None and not (within[0] <= getattr(node, "lineno", 0) <= within[1]):
            continue
        if isinstance(node, ast.Call):
            rendered = ast.unparse(node.func)
            if rendered in FORBIDDEN_CALLS or "chat.completions" in rendered:
                out.append(f"line {node.lineno}: calls {rendered}")
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            targets = [getattr(node, "module", None) or "", *(a.name for a in node.names)]
            for target in targets:
                if target in FORBIDDEN_MODULES or target.startswith("ai.providers."):
                    out.append(f"line {node.lineno}: imports {target}")
    return out


def _bounds(index, func_name: str) -> tuple[int, int]:
    found = [(f[0], f[1]) for f in index.funcs if f[2] == func_name]
    assert len(found) == 1, f"{func_name}: expected exactly one definition, got {len(found)}"
    return found[0]


def test_closed_product_endpoints_reach_the_unified_boundary(index):
    for func_name, boundaries in CLOSED_ENDPOINTS.items():
        reachable = [b for b in boundaries if index.calls_in(func_name, b)]
        assert reachable, (
            f"{func_name} is declared CLOSED but reaches none of {boundaries}")


def test_closed_product_endpoints_cannot_reach_a_provider(index):
    for func_name in CLOSED_ENDPOINTS:
        violations = _provider_violations(index.tree, _bounds(index, func_name))
        assert not violations, (
            f"{func_name} is declared CLOSED but reaches a provider: {violations}")


def test_closed_product_modules_use_the_orchestrator_only():
    for rel, label in CLOSED_MODULES.items():
        text = (BACKEND_DIR / rel).read_text(encoding="utf-8")
        violations = _provider_violations(ast.parse(text))
        assert not violations, f"{label} ({rel}) reaches a provider: {violations}"
        assert any(token in text for token in BOUNDARY_TOKENS), (
            f"{label} ({rel}) does not go through the unified AI boundary")
