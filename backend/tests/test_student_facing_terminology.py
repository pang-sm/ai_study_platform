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

# The one sentence a student is allowed to read about how it was computed.
STUDENT_SENTENCE = "基于你的真实学习记录计算。它不参与判分，也不会改写你的知识状态、错题或学习计划。"


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
        assert STUDENT_SENTENCE in document, f"{name} does not carry the allowed sentence"
    # The rule has to SAY that the internal terms stay out of the student UI, not merely imply it
    # by using the right word in one place.
    assert "不得直接展示在学生端" in SSOT
    assert "不得直接展示在学生端" in CLAUDE or "不得进入学生可见文案" in CLAUDE


def test_the_rule_did_not_weaken_the_scientific_guarantees():
    """Separating wording from semantics must not relax the science."""
    for forbidden in ("掌握率", "能力预测", "掌握概率"):
        assert forbidden in CLAUDE, f"the forbidden-phrasing list lost {forbidden}"
    assert "≠ neural network" in CLAUDE
