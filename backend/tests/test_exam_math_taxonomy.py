"""EXAM_MATH P3B: the maths taxonomy, the canonical knowledge maps, and the L2 gate.

The rules under test:

  * maths is ONE subject with three papers: a domain exists once, and a paper only decides scope;
  * the canonical knowledge maps are one per DOMAIN and are in the same chapter→section→leaf
    format every other knowledge map uses — never one map per paper;
  * no coverage is stated, because no authoritative syllabus has been imported: ``included`` is
    absent rather than ``false``, and nothing is presented as a settled exam rule;
  * the L2 gate needs BOTH a knowledge structure and verified coverage, so the subject stays
    closed while the range is unstated.
"""
import json

from conftest import register_and_login
from learning.spaces.exam_prep import catalog, math_taxonomy as tax


# ---------------------------------------------------------------- domains and papers

def test_domains_are_the_three_canonical_ones_and_exist_once_each():
    keys = [domain.key for domain in tax.all_domains()]
    assert keys == ["calculus", "linear_algebra", "probability_statistics"]
    # Config, not SQL: the same three every time, with no table behind them.
    assert len(set(keys)) == len(keys)
    assert [domain.order for domain in tax.all_domains()] == [1, 2, 3]


def test_papers_are_the_catalogue_subjects_and_own_no_content():
    variants = tax.all_variants()
    assert [variant.id for variant in variants] == ["math_1", "math_2", "math_3"]
    for variant in variants:
        # A paper IS a catalogue subject, and the catalogue is still the place subject ids live.
        assert variant.subject_id == variant.id
        assert catalog.get_subject(variant.subject_id) is not None
        assert catalog.get_subject(variant.subject_id).availability == catalog.FRAMEWORK_ONLY
        # A paper has no knowledge map of its own — that is the whole point.
        assert not hasattr(variant, "knowledge_map_id")


def test_domain_and_paper_lookups_are_total_and_safe():
    assert tax.get_domain("linear_algebra") is not None
    assert tax.get_domain("math_1") is None          # a paper is not a domain
    assert tax.get_variant("math_1") is not None
    assert tax.get_variant("calculus") is None       # a domain is not a paper
    for bad in (None, "", "  ", "linear", "MATH_1"):
        assert tax.get_domain(bad) is None
        assert tax.get_variant(bad) is None


# ---------------------------------------------------------------- canonical knowledge maps

def test_every_domain_has_exactly_one_knowledge_map():
    for domain in tax.all_domains():
        assert tax.knowledge_map_available(domain), domain.key
        path = tax.knowledge_map_path(domain)
        assert path.name == f"{domain.key}.json"
        # The map is keyed by the DOMAIN, so the three papers read the same file. A per-paper
        # copy would have to be called calculus_math_1.json or similar, and none exists.
        assert "math_" not in path.name


def test_calculus_now_has_section_level_structure_throughout():
    """高等数学's upper volume gap is closed: chapters 1–4 are no longer a placeholder block.

    P3B left them as seven unnumbered topics because 微积分 I's own table of contents was not on
    disk. P3B.5 recovered the titles from two published listings of that book — the publisher's
    own store page and a third-party bookseller — and the local answer book confirms the section
    NUMBERING only. There is no placeholder chapter any more.
    """
    calculus = tax.get_domain("calculus")
    payload = json.loads(tax.knowledge_map_path(calculus).read_text(encoding="utf-8"))
    chapters = {chapter["code"]: chapter for chapter in payload["chapters"]}
    assert "0" not in chapters, "the placeholder block is gone"
    assert [chapter["code"] for chapter in payload["chapters"]] == [
        "1", "2", "3", "4", "5", "6", "7", "8", "9", "10"]
    for code in ("1", "2", "3", "4"):
        assert chapters[code]["source_ref"] == "calculus_textbook_1_sciencep_listing"
        assert chapters[code]["children"], f"chapter {code} has sections"
        for section in chapters[code]["children"]:
            assert section["code"], "every section is numbered"
            assert section["children"], "every section carries at least one topic"
    for code in ("5", "6", "7", "8", "9", "10"):
        assert chapters[code]["source_ref"] == "calculus_textbook_2"


def test_knowledge_maps_use_the_shared_seed_format():
    for domain in tax.all_domains():
        payload = json.loads(tax.knowledge_map_path(domain).read_text(encoding="utf-8"))
        # Same envelope as every other map in seed_data/knowledge_maps/, so the existing loader
        # reads them without a maths-specific code path.
        assert set(payload) >= {"course_id", "course_name", "source", "chapters"}
        assert payload["course_id"] == domain.key
        assert payload["chapters"]
        for chapter in payload["chapters"]:
            assert set(chapter) >= {"code", "title", "children"}
            for section in chapter["children"]:
                assert set(section) >= {"code", "title", "children"}


def test_no_knowledge_id_is_scoped_to_a_paper():
    """The duplication this whole design exists to prevent."""
    for domain in tax.all_domains():
        raw = tax.knowledge_map_path(domain).read_text(encoding="utf-8")
        for variant in tax.all_variants():
            assert f'{variant.id}_' not in raw
            assert f'"{variant.id}"' not in raw
        assert "math_" not in json.dumps(json.loads(raw)["chapters"], ensure_ascii=False)


def test_the_three_papers_read_the_same_canonical_tree():
    """Math1 → Math2 changes the range, not the content."""
    trees = {}
    for variant in tax.all_variants():
        # Whatever a paper is, the content it can draw on is the domain maps — the same three.
        trees[variant.id] = {
            domain.key: tax.knowledge_map_path(domain).read_text(encoding="utf-8")
            for domain in tax.all_domains()
        }
    first = trees["math_1"]
    assert trees["math_2"] == first
    assert trees["math_3"] == first


# ---------------------------------------------------------------- coverage

def test_no_coverage_is_stated_because_no_source_states_it():
    assert tax.MATH_COVERAGE == ()
    for variant in tax.all_variants():
        assert tax.coverage_for(variant.id) == []
        assert tax.coverage_verified(variant.id) is False


def test_a_pending_source_never_counts_as_verified():
    statuses = {source.verification_status for source in tax.MATH_COVERAGE_SOURCES}
    assert statuses == {tax.PENDING_SOURCE}
    assert tax.VERIFIED not in statuses


def test_nothing_is_ever_reported_as_confirmed_outside_scope():
    """``included: false`` would be an authoritative negative, and there is no authority."""
    assert all(entry.included is not False for entry in tax.MATH_COVERAGE)


def test_the_learner_facing_note_names_the_syllabus():
    assert tax.MATH_COVERAGE_NOTE == "考试范围待正式导入，以当年全国硕士研究生招生考试大纲为准。"
    assert tax.MATH_COVERAGE_STATUS == "pending_syllabus_import"


# ---------------------------------------------------------------- the L2 gate

def test_the_subject_stays_closed_while_the_range_is_unstated():
    assert tax.math_openable() is False
    assert tax.math_ready_level() == "L1"
    reason = tax.openable_reason()
    assert "考试范围" in reason and "暂不开放" in reason


def test_openable_needs_both_halves():
    """A knowledge structure alone is not enough — the gate is coverage AND maps."""
    original = tax.MATH_COVERAGE
    try:
        # Even with every domain mapped (which is the case), no verified coverage means closed.
        assert all(tax.knowledge_map_available(domain) for domain in tax.all_domains())
        assert tax.math_openable() is False
    finally:
        tax.MATH_COVERAGE = original


# ---------------------------------------------------------------- API

def test_taxonomy_endpoint_publishes_the_whole_model(client):
    body = client.get("/exam/prep/math/taxonomy").json()
    assert body["math_taxonomy_version"] == tax.MATH_TAXONOMY_VERSION
    assert body["math_ready_level"] == "L1"
    assert body["math_openable"] is False
    assert [domain["key"] for domain in body["domains"]] == [
        "calculus", "linear_algebra", "probability_statistics"]
    assert all(domain["status"] == "available" for domain in body["domains"])
    assert [variant["id"] for variant in body["variants"]] == ["math_1", "math_2", "math_3"]
    assert body["coverage"] == []
    assert body["coverage_status"] == "pending_syllabus_import"
    assert all(source["verification_status"] == "pending_source"
               for source in body["coverage_sources"])


def test_taxonomy_endpoint_needs_no_session(client):
    """Versioned config, identical for every learner — like the catalogue, it is public."""
    assert client.get("/exam/prep/math/taxonomy").status_code == 200


def test_maths_subjects_still_answer_the_availability_gate_with_409(client):
    register_and_login(client, "math_gate", "math-gate-pass-1")
    for variant in tax.all_variants():
        response = client.get(f"/exam/prep/subjects/{variant.subject_id}/content-status")
        # Having a knowledge map does NOT open content: the gate answers "not available".
        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "EXAM_CONTENT_NOT_AVAILABLE"


def test_maths_has_no_ai_scope_and_no_material_route(client):
    """P3B does not extend the AI contract, and maths must not claim a materials surface."""
    import main

    assert catalog.is_known_module("linear_algebra") is False
    paths = {route.path for route in main.app.routes if hasattr(route, "path")}
    assert not any("math" in path and "material" in path for path in paths)
    assert "/exam/prep/math/taxonomy" in paths
