"""CS408 concept-coverage audit — a MEASUREMENT, not a repair (ACCEL_SPRINT_S6 PART I).

THE QUESTION THIS ANSWERS
-------------------------
A knowledge-tracing model can only be trained on the concept level its facts actually
carry. So the practical question "how soon could the product train its own KT model?"
reduces to "how much of the content can produce a fact with a stable native concept
identity?" — and that is measurable today, from the question bank, before a single
interaction is recorded.

WHAT IS MEASURED, AND AGAINST WHAT
----------------------------------
Coverage is measured against the product's OWN canonical concept space: the knowledge-map
seeds under ``backend/seed_data/knowledge_maps/<module>_11408.json``, whose leaf ``code``
values are the ids a chapter-practice fact stores in ``knowledge_point_id``. A question
"carries" a concept only when the id it stores EQUALS a canonical leaf code. Nothing is
normalised, matched fuzzily, stripped of a title, or inferred — a near-match is an
unresolved question, and reporting it as resolved is the corruption this audit exists to
detect.

The three levels reported are the three the product can actually group at:

    module only   the fact carries ``exam_module_id`` and nothing below it
    chapter       the stored code's leading segment names a real chapter of the module
    concept       the stored code IS a canonical leaf code of that module

IT DOES NOT FIX ANYTHING
------------------------
A module with low concept coverage is REPORTED, not repaired. Generating the missing
mappings would require deciding what each question is about, and the product has no fact
that says so — the same prohibition that keeps a concept reference from being derived from
a title applies here. The audit's job is to make the gap visible and correctly sized.
"""
from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session as DbSession

BACKEND_DIR = Path(__file__).resolve().parents[1]
KNOWLEDGE_MAP_SEED_DIR = BACKEND_DIR / "seed_data" / "knowledge_maps"

COVERAGE_LEVEL_MODULE = "module_only"
COVERAGE_LEVEL_CHAPTER = "chapter"
COVERAGE_LEVEL_CONCEPT = "concept"

# Why a question did not reach the concept level. Stable codes, because a report that says
# "unresolved" without saying WHY cannot be acted on.
UNRESOLVED_NO_CODE = "STORED_CONCEPT_ID_IS_EMPTY"
UNRESOLVED_NOT_A_LEAF = "STORED_ID_DOES_NOT_EQUAL_ANY_CANONICAL_LEAF_CODE"
UNRESOLVED_NO_SEED = "MODULE_HAS_NO_KNOWLEDGE_MAP_SEED"


def _seed_path(module_key: str) -> Path:
    safe = "".join(ch for ch in f"{module_key}_11408" if ch.isalnum() or ch in "_-")
    return KNOWLEDGE_MAP_SEED_DIR / f"{safe}.json"


def load_module_concepts(module_key: str) -> dict:
    """The module's canonical chapter codes and leaf concept codes, from its seed.

    A missing seed yields empty sets rather than an exception, so one module without a
    knowledge map does not stop the other three from being measured. The absence is then
    visible as ``UNRESOLVED_NO_SEED`` instead of as a silent zero.
    """
    path = _seed_path(module_key)
    if not path.exists():
        return {"seed_present": False, "chapters": set(), "concepts": set()}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"seed_present": False, "chapters": set(), "concepts": set()}

    chapters: set[str] = set()
    concepts: set[str] = set()
    for chapter in payload.get("chapters") or []:
        if not isinstance(chapter, dict):
            continue
        code = str(chapter.get("code") or "").strip()
        if code:
            chapters.add(code)
        for child in chapter.get("children") or []:
            if isinstance(child, dict) and str(child.get("code") or "").strip():
                concepts.add(str(child["code"]).strip())
    return {"seed_present": True, "chapters": chapters, "concepts": concepts}


def level_of(stored_code: str | None, concepts: dict) -> tuple[str, str | None]:
    """The deepest level one stored concept id reaches, plus why it stopped. Pure."""
    stored = (stored_code or "").strip()
    if not concepts["seed_present"]:
        return COVERAGE_LEVEL_MODULE, UNRESOLVED_NO_SEED
    if not stored:
        return COVERAGE_LEVEL_MODULE, UNRESOLVED_NO_CODE
    if stored in concepts["concepts"]:
        return COVERAGE_LEVEL_CONCEPT, None
    # A chapter is named by the leading segment of the stored code. This is a read of the
    # code the question bank already stores, not a concept assignment: it can place a
    # question in a chapter, and it can never place it in a concept.
    head = stored.split(".")[0].strip()
    if head and head in concepts["chapters"]:
        return COVERAGE_LEVEL_CHAPTER, UNRESOLVED_NOT_A_LEAF
    return COVERAGE_LEVEL_MODULE, UNRESOLVED_NOT_A_LEAF


def question_bank_coverage(db: DbSession, *, modules: tuple[str, ...] | None = None,
                           active_only: bool = True) -> dict:
    """Coverage of the CS408 question bank, per module and in total.

    Read-only. Counts QUESTIONS (the ceiling on what the content can ever produce), not
    interactions — the two are reported separately because a perfectly mapped question with
    no attempts behind it still yields no training data.
    """
    from learning.spaces.exam_prep.catalog import CS408_MODULES
    module_list = tuple(modules) if modules else tuple(CS408_MODULES)

    where = ["subject_key = :module"]
    if active_only:
        where.append("is_active = 1")
    clause = " AND ".join(where)

    per_module: dict[str, dict] = {}
    totals = {"questions": 0, COVERAGE_LEVEL_CONCEPT: 0,
              COVERAGE_LEVEL_CHAPTER: 0, COVERAGE_LEVEL_MODULE: 0}

    for module in module_list:
        concepts = load_module_concepts(module)
        rows = db.execute(
            text(f"SELECT knowledge_point_id, COUNT(*) FROM exam_question_bank "
                 f"WHERE {clause} GROUP BY knowledge_point_id"),
            {"module": module}).all()

        counts = {COVERAGE_LEVEL_CONCEPT: 0, COVERAGE_LEVEL_CHAPTER: 0,
                  COVERAGE_LEVEL_MODULE: 0}
        reasons: dict[str, int] = {}
        distinct_stored: set[str] = set()
        blank = 0
        for stored_code, n in rows:
            count = int(n or 0)
            if (stored_code or "").strip():
                distinct_stored.add(str(stored_code).strip())
            else:
                blank += count
            level, reason = level_of(stored_code, concepts)
            counts[level] += count
            if reason:
                reasons[reason] = reasons.get(reason, 0) + count

        total = sum(counts.values())
        per_module[module] = {
            "questions": total,
            "concept": counts[COVERAGE_LEVEL_CONCEPT],
            "chapter": counts[COVERAGE_LEVEL_CHAPTER],
            "module_only": counts[COVERAGE_LEVEL_MODULE],
            "concept_pct": round(100.0 * counts[COVERAGE_LEVEL_CONCEPT] / total, 2) if total else 0.0,
            "canonical_leaf_codes": len(concepts["concepts"]),
            "distinct_stored_codes": len(distinct_stored),
            "blank_stored_codes": blank,
            "unresolved_reasons": dict(sorted(reasons.items())),
            "seed_present": concepts["seed_present"],
        }
        totals["questions"] += total
        for level in (COVERAGE_LEVEL_CONCEPT, COVERAGE_LEVEL_CHAPTER, COVERAGE_LEVEL_MODULE):
            totals[level] += counts[level]

    n = totals["questions"]
    totals["concept_pct"] = round(100.0 * totals[COVERAGE_LEVEL_CONCEPT] / n, 2) if n else 0.0
    totals["chapter_pct"] = round(100.0 * totals[COVERAGE_LEVEL_CHAPTER] / n, 2) if n else 0.0
    totals["module_only_pct"] = round(100.0 * totals[COVERAGE_LEVEL_MODULE] / n, 2) if n else 0.0

    return {
        "measured_against": "backend/seed_data/knowledge_maps/<module>_11408.json leaf codes",
        "active_only": active_only,
        "identity_rule": ("a question carries a concept only when the stored id EQUALS a "
                          "canonical leaf code; near-matches are unresolved and are never "
                          "normalised into a match"),
        "repair": "NOT_PERFORMED — no mapping is generated by any model or heuristic",
        "per_module": per_module,
        "totals": totals,
        "interpretation": _interpretation(per_module),
    }


def _interpretation(per_module: dict) -> dict:
    """What the numbers mean for a future native KT model. Stated as scale, not validity."""
    weak = sorted(m for m, v in per_module.items()
                  if v["questions"] and v["concept_pct"] < 50.0)
    return {
        "concept_level_trainable_now": [m for m, v in per_module.items()
                                        if v["concept"] > 0],
        "concept_level_blocked": weak,
        "note": ("coverage is a CEILING on trainable interactions, not evidence that a "
                 "model would be any good: it counts what the content CAN carry, and says "
                 "nothing about how many attempts exist. A module that resolves only at "
                 "chapter level can still train a chapter-level model; it cannot train a "
                 "concept-level one."),
    }
