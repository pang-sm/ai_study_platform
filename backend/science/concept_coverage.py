"""CS408 concept-coverage audit + the deterministic concept-identity resolver.

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
values are the ids a chapter-practice fact stores in ``knowledge_point_id``. Nothing is
matched fuzzily, stripped of a title, or inferred — a near-match is an unresolved question,
and reporting it as resolved is the corruption this audit exists to detect.

The three levels reported are the three the product can actually group at:

    module only   the fact carries ``exam_module_id`` and nothing below it
    chapter       a canonical chapter of the module is determinable
    concept       a canonical leaf code of the module is determinable

TWO RULE SETS, BOTH EXACT-MATCH, ONE REPORTED AS BEFORE AND ONE AS AFTER (S8)
-----------------------------------------------------------------------------
S6 measured coverage under a single rule: the stored id must EQUAL a canonical leaf code.
That rule is still implemented, unchanged, as ``level_of`` / ``RULES_STRICT``.

Measurement showed that rule was reading a *formatting* defect as a *missing identity*.
Two modules' question banks were ingested from sources that wrote the canonical identity in
a different — still fully canonical — form:

    computer_network   ``knowledge_point_id`` holds ``"3.6 局域网"``, which is the
                       canonical leaf's OWN ``title`` field verbatim (``code`` = ``3.6``)
    computer_network   ``source_ref`` holds ``"chapter:3:3.6"``, a structured provenance
                       triple whose third segment is the canonical leaf code

So S8 adds two rules that resolve those forms. Both are EXACT EQUALITY against a string the
seed file itself publishes — one against the leaf's ``title``, one against a fixed-grammar
provenance triple whose chapter and code segments must agree with each other. Neither
transforms, truncates, stems or scores anything, and neither consults a model.

Three properties make this a resolution rather than a guess, and all three are MEASURED
into the report rather than asserted here:

  * **No conflict.** Where more than one rule fires on the same row they must name the same
    leaf. The audit counts rows where they disagree; the count is reported and must be 0.
  * **No over-reach.** ``computer_network``'s chapter 4 is ingested from a source whose own
    section numbering runs ``4.1``..``4.40``, and ``4.2 路由与转发`` occupies the same numeric
    slot as the canonical ``4.2 IPv4`` while meaning something else entirely. All seven
    such collisions are REJECTED — the title rule refuses them because the titles differ,
    and the source-ref rule refuses them because it requires the stored code to be
    *strictly deeper* than the leaf it names. They are reported as rejected, not dropped.
  * **Nothing is written.** This module only reads. ``exam_question_bank`` is a
    preservation-critical content table; re-keying its rows would be a destructive content
    migration for no gain, and the resolver is applied at read time so every row — past and
    future — resolves under one versioned rule.

IT DOES NOT FIX CONTENT
-----------------------
A module with low coverage is REPORTED, not repaired. Generating the missing mappings
would require deciding what each question is about, and the product has no fact that says
so — the same prohibition that keeps a concept reference from being derived from a title
applies here. The audit's job is to make the gap visible and correctly sized.
"""
from __future__ import annotations

import json
import re
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
UNRESOLVED_AMBIGUOUS = "IDENTITY_RULES_DISAGREE"

# Which rule established a concept identity. Reported per row so a reader can separate
# "the product already had it" from "the normalization recovered it".
RULE_NONE = "unresolved"
RULE_CANONICAL_LEAF_CODE = "canonical_leaf_code"
RULE_CANONICAL_LEAF_TITLE_ECHO = "canonical_leaf_title_echo"
RULE_SOURCE_REF_CHAPTER_LEAF = "source_ref_chapter_leaf"

# The rule set S6 measured with, and the rule set S8 reports. Both are exact-match; the
# difference is how many canonical spellings of the same identity are recognised.
RULES_STRICT = (RULE_CANONICAL_LEAF_CODE,)
RULES_NORMALIZING = (RULE_CANONICAL_LEAF_CODE, RULE_CANONICAL_LEAF_TITLE_ECHO,
                     RULE_SOURCE_REF_CHAPTER_LEAF)
RULE_SET_STRICT = "strict"
RULE_SET_NORMALIZING = "normalizing"

# Versioned as a whole: an identity that resolves under v1 and not under v2 is a different
# dataset, and a future KT export must be able to say which one it was built under.
NORMALIZATION_RULE_VERSION = "cs408-concept-normalization-v1"

# The one structured provenance form the source-ref rule accepts. Fixed grammar, anchored
# at both ends: anything else is not this form and is not resolved by it.
SOURCE_REF_CHAPTER_LEAF = re.compile(r"^chapter:(\d+):(.+)$")


def _seed_path(module_key: str) -> Path:
    safe = "".join(ch for ch in f"{module_key}_11408" if ch.isalnum() or ch in "_-")
    return KNOWLEDGE_MAP_SEED_DIR / f"{safe}.json"


# The chapter-practice matcher resolves one question bank row at a time, so the seed must
# not be re-read per row. Keyed by path AND the file's own mtime+size, so a rewritten seed
# (a test fixture, a content update) is picked up without any explicit invalidation call.
_SEED_CACHE: dict[str, tuple[tuple, dict]] = {}


def _seed_fingerprint(path: Path) -> tuple:
    try:
        stat = path.stat()
        return (int(stat.st_mtime_ns), stat.st_size)
    except OSError:
        return (0, -1)


def load_module_concepts(module_key: str) -> dict:
    """The module's canonical chapter codes, leaf codes and leaf titles, from its seed.

    ``titles`` maps a canonical leaf's OWN ``title`` field to its ``code``. In the CS408
    seeds that field is written ``"<code> <title>"``, so it is the exact string a question
    bank row stores when it was ingested from a source that put the identity column and the
    display title in one field. The mapping is built from the seed and is a lookup, never a
    parse: a key that is not literally present is not resolved.

    A missing seed yields empty sets rather than an exception, so one module without a
    knowledge map does not stop the other three from being measured. The absence is then
    visible as ``UNRESOLVED_NO_SEED`` instead of as a silent zero.
    """
    path = _seed_path(module_key)
    fingerprint = _seed_fingerprint(path)
    cached = _SEED_CACHE.get(str(path))
    if cached is not None and cached[0] == fingerprint:
        return cached[1]

    result = _read_module_concepts(path)
    _SEED_CACHE[str(path)] = (fingerprint, result)
    return result


def _read_module_concepts(path: Path) -> dict:
    if not path.exists():
        return {"seed_present": False, "chapters": set(), "concepts": set(), "titles": {},
                "chapter_of_leaf": {}}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"seed_present": False, "chapters": set(), "concepts": set(), "titles": {},
                "chapter_of_leaf": {}}

    chapters: set[str] = set()
    concepts: set[str] = set()
    titles: dict[str, str] = {}
    chapter_of_leaf: dict[str, str] = {}
    for chapter in payload.get("chapters") or []:
        if not isinstance(chapter, dict):
            continue
        code = str(chapter.get("code") or "").strip()
        if code:
            chapters.add(code)
        for child in chapter.get("children") or []:
            if not isinstance(child, dict):
                continue
            leaf = str(child.get("code") or "").strip()
            if not leaf:
                continue
            concepts.add(leaf)
            if code:
                chapter_of_leaf[leaf] = code
            title = str(child.get("title") or "").strip()
            # A title that merely repeats the code carries no second signal, so it is not
            # registered — the rule it would enable asserts nothing the code rule does not.
            if title and title != leaf:
                titles[title] = leaf
    return {"seed_present": True, "chapters": chapters, "concepts": concepts,
            "titles": titles, "chapter_of_leaf": chapter_of_leaf}


def level_of(stored_code: str | None, concepts: dict) -> tuple[str, str | None]:
    """The deepest level one stored concept id reaches, plus why it stopped. Pure.

    This is the S6 rule and it is deliberately left as it was: the stored id must EQUAL a
    canonical leaf code. Anything else is a near-match and stays below the concept level.
    ``RULES_STRICT`` still evaluates through here, which is what makes "before" numbers
    comparable with the ones S6 reported.
    """
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


def _code_from_source_ref(module_key: str, source_ref: str | None, knowledge_point_id: str | None,
                          concepts: dict) -> str | None:
    """The canonical leaf code named by a ``chapter:<chapter>:<code>`` provenance triple.

    Three conditions, all exact, all required:

      1. the triple's ``code`` IS a canonical leaf of this module;
      2. the triple's ``chapter`` IS that leaf's chapter — the two halves of the triple must
         agree with each other as well as with the seed;
      3. the row's stored code is **strictly deeper** than the triple's code
         (``stored == code + "." + ...``).

    Condition 3 is the one that makes this safe, and it was added because a measurement
    proved it necessary. ``computer_network``'s chapter 4 is ingested from a source whose
    own section numbering runs ``4.1``..``4.40``, and its ``4.2 路由与转发`` sits in the same
    numeric slot as the canonical ``4.2 IPv4`` while meaning something else entirely.
    Without condition 3 the triple ``chapter:4:4.2`` would have resolved that row to IPv4 —
    a fabricated concept link produced by a numeric collision. Chapters 1 and 2 are
    genuinely deeper (``1.1.1``, ``2.1.1``) and ARE subordinate to their triple's leaf, so
    the strict-descent requirement keeps them and refuses chapter 4.

    A stored code EQUAL to the triple's code therefore earns nothing from the triple: it
    must stand on its own identity, which is what the title-echo rule is for.
    """
    match = SOURCE_REF_CHAPTER_LEAF.match((source_ref or "").strip())
    if not match:
        return None
    chapter, code = match.group(1), match.group(2).strip()
    if code not in concepts["concepts"]:
        return None
    if concepts["chapter_of_leaf"].get(code) != chapter:
        return None
    stored = (knowledge_point_id or "").strip().split("；", 1)[0].split(";", 1)[0].strip()
    return code if stored.startswith(code + ".") else None


def _code_from_title(module_key: str, knowledge_point_id: str | None, concepts: dict) -> str | None:
    """The canonical leaf whose own ``title`` field the stored value repeats verbatim."""
    stored = (knowledge_point_id or "").strip()
    return concepts["titles"].get(stored) if stored else None


def resolve_identity(module_key: str, *, knowledge_point_id=None, source_ref=None,
                     concepts: dict | None = None,
                     rules: tuple[str, ...] = RULES_NORMALIZING) -> dict:
    """One question bank row's canonical identity under a named rule set. Pure, read-only.

    Returns the deepest level it reaches, the canonical leaf code when one was established,
    which rule established it, and — when more than one enabled rule fires — whether they
    agreed. Disagreement is never resolved by preference: it is reported, and the row is
    demoted to whatever the chapter level can still honestly say.
    """
    concepts = concepts if concepts is not None else load_module_concepts(module_key)
    stored = (knowledge_point_id or "").strip()

    candidates: dict[str, str] = {}
    if RULE_CANONICAL_LEAF_CODE in rules and concepts["seed_present"] and stored:
        if stored in concepts["concepts"]:
            candidates[RULE_CANONICAL_LEAF_CODE] = stored
    if RULE_CANONICAL_LEAF_TITLE_ECHO in rules and concepts["seed_present"]:
        code = _code_from_title(module_key, knowledge_point_id, concepts)
        if code:
            candidates[RULE_CANONICAL_LEAF_TITLE_ECHO] = code
    if RULE_SOURCE_REF_CHAPTER_LEAF in rules and concepts["seed_present"]:
        code = _code_from_source_ref(module_key, source_ref, knowledge_point_id, concepts)
        if code:
            candidates[RULE_SOURCE_REF_CHAPTER_LEAF] = code

    distinct = set(candidates.values())
    if len(distinct) > 1:
        # Two canonical fields name different leaves. Neither is preferred: the row keeps
        # only the level that does not depend on choosing between them.
        return {"level": _chapter_level_from(module_key, stored, source_ref, concepts),
                "canonical_code": None, "rule": RULE_NONE,
                "reason": UNRESOLVED_AMBIGUOUS, "rules_fired": sorted(candidates)}
    if distinct:
        code = distinct.pop()
        rule = next(r for r in sorted(candidates) if candidates[r] == code)
        return {"level": COVERAGE_LEVEL_CONCEPT, "canonical_code": code, "rule": rule,
                "reason": None, "rules_fired": sorted(candidates)}

    level, reason = level_of(stored, concepts)
    if level == COVERAGE_LEVEL_MODULE and _chapter_from_source_ref(source_ref, concepts):
        # The stored id says nothing, but the provenance triple still names a real chapter.
        # A chapter is the deepest claim that does not depend on the id, so it is the one
        # that survives.
        return {"level": COVERAGE_LEVEL_CHAPTER, "canonical_code": None, "rule": RULE_NONE,
                "reason": UNRESOLVED_NOT_A_LEAF, "rules_fired": []}
    return {"level": level, "canonical_code": None, "rule": RULE_NONE,
            "reason": reason, "rules_fired": []}


def _chapter_from_source_ref(source_ref: str | None, concepts: dict) -> str | None:
    """The chapter a provenance triple names, when that chapter is real for this module."""
    match = SOURCE_REF_CHAPTER_LEAF.match((source_ref or "").strip())
    if not match:
        return None
    chapter = match.group(1)
    return chapter if chapter in concepts["chapters"] else None


def _chapter_level_from(module_key, stored, source_ref, concepts) -> str:
    """The best chapter claim a row can still make once its concept claim is void."""
    head = stored.split(".")[0].strip() if stored else ""
    if head and head in concepts["chapters"]:
        return COVERAGE_LEVEL_CHAPTER
    if _chapter_from_source_ref(source_ref, concepts):
        return COVERAGE_LEVEL_CHAPTER
    return COVERAGE_LEVEL_MODULE


def canonical_leaf_code(module_key: str, *, knowledge_point_id=None, source_ref=None,
                        concepts: dict | None = None) -> str | None:
    """The canonical leaf code a question bank row legitimately carries, or ``None``.

    The single entry point for a caller that needs the identity and not the audit — the
    chapter-practice matcher reads this instead of re-implementing any of the rules.
    """
    resolved = resolve_identity(module_key, knowledge_point_id=knowledge_point_id,
                                source_ref=source_ref, concepts=concepts)
    return resolved["canonical_code"]


def question_bank_coverage(db: DbSession, *, modules: tuple[str, ...] | None = None,
                           active_only: bool = True) -> dict:
    """Coverage of the CS408 question bank, per module and in total, under both rule sets.

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
    strict_totals = {"questions": 0, "concept": 0, "chapter": 0, "module_only": 0}
    rule_totals: dict[str, int] = {rule: 0 for rule in RULES_NORMALIZING}
    corroboration = {"rows_resolved_by_two_rules": 0, "rules_disagreed": 0,
                     "chapter_segments_compared": 0, "chapter_segments_agreed": 0,
                     "rejected_near_matches": {}}

    for module in module_list:
        concepts = load_module_concepts(module)
        rows = db.execute(
            text(f"SELECT knowledge_point_id, source_ref, COUNT(*) FROM exam_question_bank "
                 f"WHERE {clause} GROUP BY knowledge_point_id, source_ref"),
            {"module": module}).all()

        counts = {COVERAGE_LEVEL_CONCEPT: 0, COVERAGE_LEVEL_CHAPTER: 0,
                  COVERAGE_LEVEL_MODULE: 0}
        strict_counts = {COVERAGE_LEVEL_CONCEPT: 0, COVERAGE_LEVEL_CHAPTER: 0,
                         COVERAGE_LEVEL_MODULE: 0}
        reasons: dict[str, int] = {}
        rules_used: dict[str, int] = {rule: 0 for rule in RULES_NORMALIZING}
        distinct_stored: set[str] = set()
        blank = 0
        for stored_code, source_ref, n in rows:
            count = int(n or 0)
            if (stored_code or "").strip():
                distinct_stored.add(str(stored_code).strip())
            else:
                blank += count

            strict_level, _ = level_of(stored_code, concepts)
            strict_counts[strict_level] += count

            resolved = resolve_identity(module, knowledge_point_id=stored_code,
                                        source_ref=source_ref, concepts=concepts)
            counts[resolved["level"]] += count
            if resolved["reason"]:
                reasons[resolved["reason"]] = reasons.get(resolved["reason"], 0) + count
            if resolved["rule"] != RULE_NONE:
                rules_used[resolved["rule"]] += count
                rule_totals[resolved["rule"]] += count
            if len(resolved["rules_fired"]) > 1:
                corroboration["rows_resolved_by_two_rules"] += count
            if resolved["reason"] == UNRESOLVED_AMBIGUOUS:
                corroboration["rules_disagreed"] += count
            if resolved["level"] == COVERAGE_LEVEL_CONCEPT:
                # Independent cross-check: the triple's CHAPTER segment is read from
                # `source_ref`, the stored code's leading segment from `knowledge_point_id`.
                # Two different columns stating the same chapter is corroboration; a row
                # where they disagree would mean the rule resolved across chapter lines.
                chapter_seg = _chapter_from_source_ref(source_ref, concepts)
                stored_head = (stored_code or "").strip().split(".", 1)[0].strip()
                if chapter_seg:
                    corroboration["chapter_segments_compared"] += count
                    if chapter_seg == stored_head:
                        corroboration["chapter_segments_agreed"] += count

            # A stored value that looks like a concept but was REJECTED is the case a reader
            # most needs to see: it is where a laxer rule would have invented a link.
            if strict_level != COVERAGE_LEVEL_CONCEPT and resolved["level"] != COVERAGE_LEVEL_CONCEPT:
                near = _near_match_code(stored_code, source_ref, concepts)
                if near:
                    key = f"{stored_code!r} -> {near}"
                    corroboration["rejected_near_matches"][key] = (
                        corroboration["rejected_near_matches"].get(key, 0) + count)

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
            # The SAME measurement under S6's single rule, kept alongside so the two are
            # comparable without re-running an older build.
            "strict": {
                "concept": strict_counts[COVERAGE_LEVEL_CONCEPT],
                "chapter": strict_counts[COVERAGE_LEVEL_CHAPTER],
                "module_only": strict_counts[COVERAGE_LEVEL_MODULE],
                "concept_pct": round(
                    100.0 * strict_counts[COVERAGE_LEVEL_CONCEPT] / total, 2) if total else 0.0,
            },
            "resolved_by_rule": dict(sorted(rules_used.items())),
        }
        totals["questions"] += total
        for level in (COVERAGE_LEVEL_CONCEPT, COVERAGE_LEVEL_CHAPTER, COVERAGE_LEVEL_MODULE):
            totals[level] += counts[level]
        strict_totals["questions"] += total
        strict_totals["concept"] += strict_counts[COVERAGE_LEVEL_CONCEPT]
        strict_totals["chapter"] += strict_counts[COVERAGE_LEVEL_CHAPTER]
        strict_totals["module_only"] += strict_counts[COVERAGE_LEVEL_MODULE]

    n = totals["questions"]
    totals["concept_pct"] = round(100.0 * totals[COVERAGE_LEVEL_CONCEPT] / n, 2) if n else 0.0
    totals["chapter_pct"] = round(100.0 * totals[COVERAGE_LEVEL_CHAPTER] / n, 2) if n else 0.0
    totals["module_only_pct"] = round(100.0 * totals[COVERAGE_LEVEL_MODULE] / n, 2) if n else 0.0
    strict_totals["concept_pct"] = (
        round(100.0 * strict_totals["concept"] / n, 2) if n else 0.0)

    return {
        "measured_against": "backend/seed_data/knowledge_maps/<module>_11408.json leaf codes",
        "active_only": active_only,
        "identity_rule": ("a question carries a concept only when a canonical leaf code is "
                          "established by EXACT equality against a string the seed itself "
                          "publishes; near-matches are unresolved and are never normalised "
                          "into a match"),
        "repair": ("NOT_PERFORMED — no mapping is generated by any model or heuristic, and "
                   "no question bank row is modified"),
        "normalization": {
            "rule_version": NORMALIZATION_RULE_VERSION,
            "rules": list(RULES_NORMALIZING),
            "strict_rules": list(RULES_STRICT),
            "before": strict_totals,
            "after": {
                "concept": totals[COVERAGE_LEVEL_CONCEPT],
                "chapter": totals[COVERAGE_LEVEL_CHAPTER],
                "module_only": totals[COVERAGE_LEVEL_MODULE],
                "concept_pct": totals["concept_pct"],
            },
            "recovered_concept_rows": totals[COVERAGE_LEVEL_CONCEPT] - strict_totals["concept"],
            "resolved_by_rule": dict(sorted(rule_totals.items())),
            "corroboration": {
                "rows_resolved_by_two_rules": corroboration["rows_resolved_by_two_rules"],
                "rules_disagreed": corroboration["rules_disagreed"],
                "chapter_segments_compared": corroboration["chapter_segments_compared"],
                "chapter_segments_agreed": corroboration["chapter_segments_agreed"],
                "rejected_near_matches": dict(sorted(
                    corroboration["rejected_near_matches"].items())),
                "note": ("`rules_disagreed` must be 0 for the normalization to be sound: "
                         "where two independent canonical fields both resolve, they must "
                         "name the same leaf. `chapter_segments_agreed` must equal "
                         "`chapter_segments_compared`: the chapter read from `source_ref` "
                         "and the chapter read from the stored id's own leading segment are "
                         "different columns, and a row where they disagreed would mean the "
                         "rule resolved across chapter lines. Rejected near-matches are "
                         "listed rather than dropped — they are where a laxer rule would "
                         "have invented a link."),
            },
        },
        "per_module": per_module,
        "totals": totals,
        "interpretation": _interpretation(per_module),
    }


def _near_match_code(stored_code, source_ref, concepts) -> str | None:
    """A canonical leaf the row ALMOST names — the near-match that stays unresolved.

    Deliberately narrow: it reports only the case where the stored value's own leading
    token IS a canonical leaf code but the value as a whole is not that leaf's identity.
    That is precisely ``"4.1 异构网络互连"`` against canonical ``4.1``, and it is what a
    reader must be able to see so the rejection is auditable.
    """
    stored = (stored_code or "").strip()
    if not stored:
        return None
    head = stored.split(" ", 1)[0].strip()
    if head in concepts["concepts"] and head != stored:
        return head
    return None


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
