"""ACCEL_PRODUCT_S8 PART 6 — canonical CS408 concept identity, and what it unblocks.

The sprint's question was "how much of the 9333-question bank can produce a fact with a
stable canonical concept identity, and can that be improved by a DETERMINISTIC
normalization rather than a model or a guess?". These tests pin the answer:

  * the S6 strict rule still behaves exactly as S6 defined it (``level_of`` unchanged);
  * the normalization recovers only forms that are EXACT EQUALITY against a string the
    seed itself publishes, and the corroboration counters prove it;
  * the collision it must refuse — ``computer_network`` chapter 4, whose own section
    numbering runs 4.1..4.40 in the same numeric slots as the canonical leaves while
    meaning something else — IS refused and IS reported;
  * the chapter-practice matcher reads the SAME resolver, so the recovered identities
    actually make questions reachable for a learner instead of only improving a metric.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from database import SessionLocal
from models import ExamQuestionBank
from science import concept_coverage as cc
import main as app_main

BACKEND_DIR = Path(__file__).resolve().parents[1]
SEED_DIR = BACKEND_DIR / "seed_data" / "knowledge_maps"

CN = "computer_network"
OS = "operating_system"


def _seed(module: str) -> dict:
    return json.loads((SEED_DIR / f"{module}_11408.json").read_text(encoding="utf-8"))


def _first_leaf(module: str) -> tuple[str, str]:
    """(canonical code, canonical title) of the module's first leaf."""
    for chapter in _seed(module)["chapters"]:
        for child in chapter.get("children") or []:
            return str(child["code"]).strip(), str(child["title"]).strip()
    raise AssertionError("seed has no leaves")


def _row(module: str, knowledge_point_id, source_ref=None) -> ExamQuestionBank:
    """An unsaved row — the matcher reads attributes only, so nothing is persisted."""
    return ExamQuestionBank(subject_key=module, subject_name=module, source_type="chapter",
                            visibility="public", knowledge_point_id=knowledge_point_id,
                            source_ref=source_ref, stem="x", is_active=True)


# ================================================================ the rules

def test_level_of_still_implements_the_s6_strict_rule():
    """The rule S6 froze is NOT relaxed. '<code> <title>' is still not a leaf code here."""
    concepts = {"seed_present": True, "chapters": {"1"}, "concepts": {"1.1", "1.2"},
                "titles": {"1.1 概述": "1.1"}, "chapter_of_leaf": {"1.1": "1", "1.2": "1"}}
    assert cc.level_of("1.1", concepts)[0] == "concept"
    assert cc.level_of("1.1 概述", concepts) == ("chapter", cc.UNRESOLVED_NOT_A_LEAF)
    assert cc.level_of("", concepts) == ("module_only", cc.UNRESOLVED_NO_CODE)
    assert cc.level_of("9.9", concepts)[0] == "module_only"


def test_the_strict_rule_set_reproduces_the_s6_measurement():
    """``RULES_STRICT`` is a real, selectable rule set — not a comment about one."""
    resolved = cc.resolve_identity(CN, knowledge_point_id="3.6 局域网",
                                   source_ref="chapter:3:3.6", rules=cc.RULES_STRICT)
    assert resolved["level"] == "chapter"
    assert resolved["canonical_code"] is None


# ================================================================ what is recovered

def test_a_canonical_title_echo_resolves_to_the_leaf_it_echoes():
    code, title = _first_leaf(CN)
    resolved = cc.resolve_identity(CN, knowledge_point_id=title)
    assert resolved["canonical_code"] == code
    assert resolved["rule"] == cc.RULE_CANONICAL_LEAF_TITLE_ECHO


def test_a_deeper_code_resolves_through_its_provenance_triple():
    """``1.1.1 <title>`` is a SUB-SECTION of canonical ``1.1``, and the triple says so."""
    chapter = _seed(CN)["chapters"][0]
    code = str(chapter["children"][0]["code"]).strip()
    resolved = cc.resolve_identity(CN, knowledge_point_id=f"{code}.1 某个子小节",
                                   source_ref=f"chapter:{chapter['code']}:{code}")
    assert resolved["canonical_code"] == code
    assert resolved["rule"] == cc.RULE_SOURCE_REF_CHAPTER_LEAF


def test_a_provenance_triple_needs_its_own_two_halves_to_agree():
    """A triple that names chapter 2 but a leaf of chapter 1 is malformed, not a match."""
    leaf = str(_seed(CN)["chapters"][0]["children"][0]["code"]).strip()
    assert cc.canonical_leaf_code(CN, knowledge_point_id=f"{leaf}.9 x",
                                  source_ref=f"chapter:2:{leaf}") is None


def test_a_stored_code_equal_to_the_triple_earns_nothing_from_the_triple():
    """The guard that makes the triple rule safe: it must not be a numeric collision.

    ``chapter:4:4.2`` beside a stored ``4.2 <something else>`` is exactly how a fabricated
    link would be produced, so a stored code EQUAL to the triple's code resolves nothing
    through the triple and must stand on its own identity.
    """
    canonical_42 = None
    for chapter in _seed(CN)["chapters"]:
        for child in chapter.get("children") or []:
            if str(child["code"]).strip() == "4.2":
                canonical_42 = str(child["title"]).strip()
    assert canonical_42 is not None, "fixture assumes canonical 4.2 exists"

    # the collision: same numeric slot, different topic
    assert cc.canonical_leaf_code(CN, knowledge_point_id="4.2 路由与转发",
                                 source_ref="chapter:4:4.2") is None
    # the same slot resolving honestly, via the canonical title
    assert cc.canonical_leaf_code(CN, knowledge_point_id=canonical_42,
                                 source_ref="chapter:4:4.2") == "4.2"


def test_a_module_without_a_seed_resolves_nothing_rather_than_guessing(db_session):
    assert cc.load_module_concepts("no_such_module")["seed_present"] is False
    assert cc.canonical_leaf_code("no_such_module", knowledge_point_id="1.1") is None


# ================================================================ the real bank

def _shipped_bank_report():
    """The coverage report, but ONLY when the real shipped content is what is being read.

    The test database is not the product's content: the suite's own fixtures seed small
    invented banks, and a test about the shipped 9333-question bank must not silently
    report on those instead. The presence check is therefore for the SHAPE the real content
    has — a `computer_network` row whose stored id echoes a canonical leaf title — and not
    merely for a non-empty table.
    """
    db = SessionLocal()
    try:
        report = cc.question_bank_coverage(db, active_only=False)
        from sqlalchemy import text
        echo_rows = db.execute(text(
            "SELECT COUNT(*) FROM exam_question_bank "
            "WHERE subject_key = 'computer_network' AND knowledge_point_id LIKE '3.6 %'"
        )).scalar()
    finally:
        db.close()
    if report["totals"]["questions"] == 0 or not echo_rows:
        pytest.skip("the shipped question bank is not present in this environment")
    return report


def test_the_real_bank_resolves_with_no_rule_disagreement_and_no_silent_rejection():
    """Measured against the SHIPPED content, not a fixture.

    The two corroboration counters are the proof that this is a resolution and not a
    guess: two independent rules never name different leaves, and every near-match the
    normalization refused is LISTED rather than dropped.
    """
    report = _shipped_bank_report()
    corr = report["normalization"]["corroboration"]
    assert corr["rules_disagreed"] == 0
    assert corr["chapter_segments_compared"] == corr["chapter_segments_agreed"]
    assert corr["chapter_segments_compared"] > 0
    assert corr["rejected_near_matches"], (
        "computer_network chapter 4's numbering collision must be refused AND reported")


def test_the_normalization_recovers_but_cannot_invent():
    """``after`` is never below ``before``, and the recovered rows are attributable."""
    report = _shipped_bank_report()
    norm = report["normalization"]
    assert norm["after"]["concept"] >= norm["before"]["concept"]
    assert norm["recovered_concept_rows"] == (
        norm["after"]["concept"] - norm["before"]["concept"])
    assert norm["recovered_concept_rows"] == sum(
        norm["resolved_by_rule"][r] for r in norm["rules"]
        if r != cc.RULE_CANONICAL_LEAF_CODE)
    assert norm["rule_version"] == cc.NORMALIZATION_RULE_VERSION
    # the audit still states it repairs nothing
    assert "NOT_PERFORMED" in report["repair"]


def test_the_audit_never_writes_to_the_question_bank():
    """The resolver is READ-TIME. Re-keying 9333 preservation-critical content rows would
    be a destructive content migration for no gain."""
    db = SessionLocal()
    try:
        before = cc.question_bank_coverage(db, active_only=False)["per_module"]
        after = cc.question_bank_coverage(db, active_only=False)["per_module"]
    finally:
        db.close()
    assert before == after


# ================================================================ reachability

def test_the_chapter_practice_matcher_reads_the_same_resolver():
    """A metric that improves while the learner still sees zero questions is worthless.

    ``computer_network``'s bank stores ``"3.6 局域网"`` where the knowledge map's leaf code
    is ``3.6``, and before S8 that made all 920 of its questions unreachable.
    """
    chapter = _seed(CN)["chapters"][2]
    leaf = str(chapter["children"][0]["code"]).strip()
    title = str(chapter["children"][0]["title"]).strip()

    row = _row(CN, title, source_ref=f"chapter:{chapter['code']}:{leaf}")
    assert app_main._chapter_question_matches_kp(row, leaf) is True

    # and the refused collision stays unreachable, which is the point of refusing it
    collision = _row(CN, "4.2 路由与转发", source_ref="chapter:4:4.2")
    assert app_main._chapter_question_matches_kp(collision, "4.2") is False


def test_reachability_does_not_regress_for_a_module_that_was_already_canonical():
    chapter = _seed(OS)["chapters"][0]
    leaf = str(chapter["children"][0]["code"]).strip()
    assert app_main._chapter_question_matches_kp(_row(OS, leaf), leaf) is True


def test_a_row_with_no_identity_contributes_nothing():
    assert app_main._question_canonical_leaf_codes(_row(CN, "")) == ()
    assert app_main._question_canonical_leaf_codes(_row(CN, "4.10 IPv4 地址",
                                                        source_ref="chapter:4:4.10")) == ()


def test_the_seed_cache_is_invalidated_by_a_rewritten_seed(tmp_path, monkeypatch):
    """A cached seed that outlives its file would make a content update invisible."""
    seed = tmp_path / "cache_probe_11408.json"
    seed.write_text(json.dumps({"chapters": [
        {"code": "1", "children": [{"code": "1.1", "title": "1.1 A"}]}]}), encoding="utf-8")
    monkeypatch.setattr(cc, "KNOWLEDGE_MAP_SEED_DIR", tmp_path)
    assert cc.load_module_concepts("cache_probe")["concepts"] == {"1.1"}

    seed.write_text(json.dumps({"chapters": [
        {"code": "1", "children": [{"code": "1.1", "title": "1.1 A"},
                                   {"code": "1.2", "title": "1.2 B"}]}]}), encoding="utf-8")
    assert cc.load_module_concepts("cache_probe")["concepts"] == {"1.1", "1.2"}
