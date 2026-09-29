"""PHASE 3B — the OCR decision must be explicit, and must not change behaviour.

WHAT WAS COUPLED. ``_ocr_year_questions`` branched on ``bool(image_urls)``, so "where this
question's source image lives" and "does this question need image OCR" were the same field. The
branch structure also reached the same no-OCR outcome from two states that MEAN different things:

  * no source image          -> no OCR, text from the document, not flagged
  * source image unreadable  -> no OCR, text from the document, FLAGGED for review

One boolean cannot carry those three outcomes, which is why they are now two predicates
(:func:`has_source_image` and :func:`requires_image_ocr`) rather than one truthiness test.

WHAT MUST NOT CHANGE. The decision itself. Nothing below asserts that the new fields are "nicer" —
it asserts they reproduce, record for record, what the code already did.
"""
from __future__ import annotations

import json
from pathlib import Path

import exam_paper_parser as parser

CACHE = Path(parser.CACHE_DIR)
STATIC = Path(parser.STATIC_DIR)


def _cached_source_questions():
    """Every (subject, year, question) in the docx-parse caches — the OCR decision's real input."""
    for subject_dir in sorted(p for p in CACHE.iterdir() if p.is_dir()):
        parsed_file = subject_dir / "parsed.json"
        if not parsed_file.exists():
            continue
        parsed = json.loads(parsed_file.read_text(encoding="utf-8"))
        for year, questions in parsed.items():
            if str(year).startswith("_") or not isinstance(questions, list):
                continue
            for question in questions:
                yield subject_dir.name, int(year), question


# ── B4/B6.1: the new decision reproduces the old one, on every real record ─────────

def test_the_new_decision_matches_the_legacy_decision_on_every_cached_record():
    compared = 0
    for subject, year, question in _cached_source_questions():
        legacy = parser._legacy_ocr_decision(subject, year, question)
        new = parser.requires_image_ocr(subject, year, question)
        assert legacy == new, (
            f"{subject} {year} Q{question.get('number')}: legacy={legacy} new={new}")
        compared += 1
    assert compared > 0, "no cached source question was exercised"


# ── B6.2/3/4: the three outcomes stay distinct ──────────────────────────────────────

def test_a_readable_source_image_requires_ocr(tmp_path, monkeypatch):
    monkeypatch.setattr(parser, "STATIC_DIR", tmp_path)
    (tmp_path / "operating_system" / "2022").mkdir(parents=True)
    (tmp_path / "operating_system" / "2022" / "img_1.jpg").write_bytes(b"x")
    question = {"number": 25, "image_urls": ["/static/exam_papers/11408/operating_system/2022/img_1.jpg"]}
    assert parser.has_source_image(question) is True
    assert parser.requires_image_ocr("operating_system", 2022, question) is True


def test_a_missing_source_image_does_not_require_ocr(tmp_path, monkeypatch):
    """The middle case. It must NOT be treated as text-only, because it is flagged for review."""
    monkeypatch.setattr(parser, "STATIC_DIR", tmp_path)
    question = {"number": 25, "image_urls": ["/static/exam_papers/11408/operating_system/2022/absent.jpg"]}
    assert parser.has_source_image(question) is True
    assert parser.requires_image_ocr("operating_system", 2022, question) is False


def test_a_question_with_no_source_image_does_not_require_ocr():
    question = {"number": 7, "content": "一棵二叉搜索树如图 7 所示"}
    assert parser.has_source_image(question) is False
    assert parser.requires_image_ocr("data_structure", 2024, question) is False


def test_the_three_outcomes_are_three_not_two(tmp_path, monkeypatch):
    """A single boolean could not tell "no image" from "unreadable image" — this is why there are
    two fields, and it is the property that would regress if someone merged them."""
    monkeypatch.setattr(parser, "STATIC_DIR", tmp_path)
    no_image = {"number": 1}
    unreadable = {"number": 2, "image_urls": ["/static/exam_papers/11408/data_structure/2024/nope.jpg"]}
    assert parser.requires_image_ocr("data_structure", 2024, no_image) == \
        parser.requires_image_ocr("data_structure", 2024, unreadable) is False
    assert parser.has_source_image(no_image) != parser.has_source_image(unreadable)


# ── B6.9: a stem that merely mentions a figure must not decide anything ────────────

def test_a_stem_mentioning_a_figure_does_not_itself_require_image_ocr():
    """`data_structure 2026 Q7` says 「图中每条边有一个字符」 and has no figure at all. Prose must
    never drive the OCR decision — only the source material does."""
    question = {"number": 7, "content": "设有向图……图中每条边有一个字符"}
    assert parser.has_source_image(question) is False
    assert parser.requires_image_ocr("data_structure", 2026, question) is False


# ── B5: provenance is kept, not deleted ────────────────────────────────────────────

def test_source_image_urls_are_still_recorded_after_the_split():
    """The decision no longer depends on `image_urls`; it is retained because it is the only
    record of where the OCR input came from. Deleting it to reach a rounder number would destroy
    provenance, so this test exists to fail if someone does."""
    with_urls = sum(1 for _s, _y, q in _cached_source_questions() if q.get("image_urls"))
    assert with_urls > 0, "source image provenance was dropped from the caches"


# ── B7: OCR source images must never reach the learner ─────────────────────────────

def test_a_source_image_that_exists_only_under_static_is_not_servable():
    """Two asset systems, kept apart.

    `static/exam_papers/11408/…` holds real files and they are OCR inputs; the figure resolver
    must not be able to reach them, whatever the caches say. This asserts on a file that genuinely
    exists there, so it fails if the resolver is ever widened back to that tree.
    """
    import exam_past_paper

    static_copy = STATIC / "operating_system" / "2022" / "img_14.jpg"
    assert static_copy.exists(), "the fixture file moved; pick another real static-tree image"
    assert exam_past_paper.resolve_resource_file("operating_system", 2022, "img_14.jpg") is None

    served = Path(exam_past_paper.EXAM_RESOURCES_DIR) / "operating_system" / "past_papers" / "figures"
    assert served != STATIC, "the served figure root must not be the OCR source tree"
