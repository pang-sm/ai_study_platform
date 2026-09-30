"""The internal definition and the student-facing wording are two different things.

WHAT THIS HOLDS
---------------
The learning-state component is, internally, a deterministic state engine that belongs to the
scientific runtime. Those are real technical definitions and they stay in the governance
documents — deleting them would erase what the component IS and how it is productized.

What changed is only the Wording: a student reads 学习状态, not the name of the engine that
produced it. This test holds both halves of that, because either half failing is a real
regression:

  * the internal vocabulary is still defined (a future edit cannot quietly drop it);
  * the student-facing rule is still stated, so the boundary does not depend on anyone
    remembering it.
"""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SSOT = (REPO_ROOT / "ZHIXUE_AI_PRODUCT_REDESIGN_SSOT.md").read_text(encoding="utf-8")
CLAUDE = (REPO_ROOT / "CLAUDE.md").read_text(encoding="utf-8")

# The engineering vocabulary. Kept on purpose — see the module docstring.
INTERNAL_TERMS = ("确定性学习状态引擎（实验）", "Student Twin", "Scientific Runtime")

# 2026-09-30: the page is a formal product surface, so it carries NO explanation of how the
# numbers were produced. This is the sentence that used to be MANDATORY on it — it must now be
# absent from both governance documents, and the two rules that replaced it must be stated.
RETIRED_STUDENT_SENTENCE = ("基于你的真实学习记录计算。它不参与判分，"
                            "也不会改写你的知识状态、错题或学习计划。")


def test_the_internal_definitions_are_still_defined():
    for term in INTERNAL_TERMS:
        assert term in SSOT, f"the SSOT no longer defines {term}"
    # The hard invariants are permanent and must not have been trimmed along with the wording.
    assert "controls_product_decision = false" in SSOT
    assert "writes_learner_fact = false" in SSOT


def test_the_student_facing_rule_is_stated_in_both_governance_documents():
    for document, name in ((SSOT, "SSOT"), (CLAUDE, "CLAUDE.md")):
        assert "学生端" in document, f"{name} does not state a student-facing rule"
        assert "学习状态" in document, f"{name} does not name the student-facing term"
        # The rule that REPLACED the verbatim sentence: the student page explains nothing about
        # how its numbers were produced.
        assert "不得出现关于实现方式的说明句" in document, \
            f"{name} does not forbid an implementation explanation on the student page"
    # The rule has to SAY that the internal terms stay out of the student UI, not merely imply it
    # by using the right word in one place.
    assert "不得直接展示在学生端" in SSOT, SSOT
    assert "不得直接展示在学生端" in CLAUDE or "不得进入学生可见文案" in CLAUDE


def test_the_retired_sentence_is_no_longer_required():
    """The page stopped explaining itself; the documents must not still demand it.

    Deleting it from the UI while a governance file still requires it would leave the next
    person to re-add it, which is exactly the failure this round corrects. So the guard is on
    the sentence itself: it must be absent from BOTH documents. Each document records the
    removal by quoting the retired RULE's name, but neither may carry the sentence as copy.
    """
    for document, name in ((SSOT, "SSOT"), (CLAUDE, "CLAUDE.md")):
        assert RETIRED_STUDENT_SENTENCE not in document, \
            f"{name} still carries the retired student-facing sentence"
    # ...and the removal is recorded as a decision, so the remaining mention cannot be mistaken
    # for a live requirement.
    assert "修订说明" in SSOT and "2026-09-30" in SSOT
    assert "已于 2026-09-30" in CLAUDE


def test_the_runtime_role_is_optional_and_non_blocking():
    for document, name in ((SSOT, "SSOT"), (CLAUDE, "CLAUDE.md")):
        assert "optional_non_blocking_enhancement" in document, \
            f"{name} does not state the runtime's non-blocking role"
    # SSOT must state the consequences, not just the label.
    assert "页面可用性不依赖 scientific runtime" in SSOT
    assert "用户不需要知道 scientific runtime 的存在" in SSOT
    assert "不能决定页面是否可用" in SSOT


def test_the_rule_did_not_weaken_the_scientific_guarantees():
    """Separating wording from semantics must not relax the science."""
    for forbidden in ("掌握率", "能力预测", "掌握概率"):
        assert forbidden in CLAUDE, f"the forbidden-phrasing list lost {forbidden}"
    assert "≠ neural network" in CLAUDE
