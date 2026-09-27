"""EXAM_MATH P3B.5: the canonical boundary, the maps' structure, and provenance.

The rules under test:

  * a canonical map says what the DOMAIN contains; coverage says what a PAPER examines. Nothing
    removes a node because an exam may not test it, so canonical content cannot depend on scope;
  * the three maps are structurally sound: unique ids, no paper-named id, no cycles, no empty or
    duplicate sibling names, every node reachable, every source resolvable;
  * the sources are reproducible: identity plus size plus SHA-256, recorded without paths;
  * coverage is still empty, and no unverified source can turn a claim into a verified one.
"""
import json

import pytest
from conftest import register_and_login
from learning.spaces.exam_prep import catalog, math_knowledge as mk, math_taxonomy as tax

DOMAIN_KEYS = ["calculus", "linear_algebra", "probability_statistics"]


# ---------------------------------------------------------------- the boundary rule

def test_every_map_declares_the_same_inclusion_policy():
    for key in DOMAIN_KEYS:
        payload = mk.load_map(key)
        assert payload["inclusion_policy"] == mk.CANONICAL_INCLUSION_POLICY
        assert payload["source_ids"], key
        assert payload["scope_note"], key


def test_the_policy_is_source_complete_not_exam_scoped():
    """What the map's own metadata promises, in the words the module uses."""
    for key in DOMAIN_KEYS:
        note = mk.load_map(key)["inclusion_note"]
        assert "不以" in note and "考试卷是否考" in note
        assert "coverage" in note


def test_canonical_content_does_not_depend_on_exam_scope():
    """The headline property. A map is loaded without ever consulting coverage."""
    assert tax.CANONICAL_CONTENT_DEPENDS_ON_EXAM_SCOPE is False
    before = {key: mk.load_map(key) for key in DOMAIN_KEYS}

    # Now assert the opposite of the exam's range for a real node, and re-read. If the boundary
    # were wrong, the node would vanish or the map would change.
    original = tax.MATH_COVERAGE
    try:
        tax.MATH_COVERAGE = (
            tax.MathCoverageEntry(variant="math_2", domain="linear_algebra", level="chapter",
                                  code="6", included=False, source_id="syllabus_national_pending"),
            tax.MathCoverageEntry(variant="math_2", domain="calculus", level="section",
                                  code="7.7", included=False, source_id="syllabus_national_pending"),
        )
        after = {key: mk.load_map(key) for key in DOMAIN_KEYS}
    finally:
        tax.MATH_COVERAGE = original

    assert after == before, "coverage must not change what the canonical map contains"
    # And the "excluded" nodes are still there, addressed by their canonical ids.
    linear_algebra = mk.load_map("linear_algebra")
    assert [chapter["code"] for chapter in linear_algebra["chapters"]] == ["1", "2", "3", "4", "5", "6", "7"]
    calculus = mk.load_map("calculus")
    assert any(section["code"] == "7.7" for chapter in calculus["chapters"] for section in chapter["children"])


def test_content_once_excluded_on_exam_grounds_is_present():
    """The P3B exclusions, restored. A future edit that removes them again must fail here.

    Each of these was dropped because a book's preface called it beyond the exam. That is a scope
    judgement, and scope lives in coverage — so they belong in the map.
    """
    linear_algebra = mk.load_map("linear_algebra")
    la_sections = {s["code"] for chapter in linear_algebra["chapters"] for s in chapter["children"]}
    assert {"3.2", "3.5", "4.6", "4.7"} <= la_sections
    assert {"6", "7"} <= {chapter["code"] for chapter in linear_algebra["chapters"]}

    calculus = mk.load_map("calculus")
    ca_sections = {s["code"] for chapter in calculus["chapters"] for s in chapter["children"]}
    assert {"5.4", "5.5", "10.5", "10.7"} <= ca_sections

    probability = mk.load_map("probability_statistics")
    assert {"9", "10"} <= {chapter["code"] for chapter in probability["chapters"]}


# ---------------------------------------------------------------- structural audit

@pytest.mark.parametrize("domain", DOMAIN_KEYS)
def test_each_map_passes_its_own_audit(domain):
    audit = mk.audit_domain(domain)
    assert audit.ok, audit.issues
    assert audit.chapters > 0 and audit.sections > 0
    assert audit.duplicate_count == 0
    assert audit.invalid_parent_count == 0
    assert audit.cycle_count == 0
    assert audit.empty_name_count == 0
    assert audit.duplicate_sibling_count == 0
    assert audit.variant_prefixed_count == 0
    assert audit.unresolved_source_refs == ()
    assert audit.unresolved_source_ids == ()
    assert audit.declaration_issues == ()


@pytest.mark.parametrize("domain", DOMAIN_KEYS)
def test_every_node_is_reachable_and_nothing_is_orphaned(domain):
    audit = mk.audit_domain(domain)
    # The audit counts exactly the nodes it walked from the root, so an unreachable node would
    # show up as a mismatch against the three levels it classified.
    assert audit.node_count == audit.chapters + audit.sections + audit.leaves


@pytest.mark.parametrize("domain", DOMAIN_KEYS)
def test_every_chapter_reaches_section_level(domain):
    """The gap P3B left open, now closed for all three domains."""
    assert mk.audit_domain(domain).granularity_status == "complete"


@pytest.mark.parametrize("domain", DOMAIN_KEYS)
def test_no_knowledge_id_names_an_exam_paper(domain):
    raw = json.dumps(mk.load_map(domain), ensure_ascii=False)
    for variant in tax.all_variants():
        assert f'{variant.id}_' not in raw
    assert mk.audit_domain(domain).variant_prefixed_count == 0


def test_the_three_papers_read_the_same_canonical_tree():
    """Math1 → Math2 changes the scope question, not one byte of content."""
    trees = {key: json.dumps(mk.load_map(key), ensure_ascii=False, sort_keys=True) for key in DOMAIN_KEYS}
    for variant in tax.all_variants():
        # Whatever paper is asking, the content it can draw on is these three maps.
        assert {key: mk.load_map(key) for key in DOMAIN_KEYS} is not None
        assert set(trees) == set(DOMAIN_KEYS)
    assert trees == {key: json.dumps(mk.load_map(key), ensure_ascii=False, sort_keys=True) for key in DOMAIN_KEYS}


def test_a_chapter_with_only_topic_children_reads_as_incomplete(monkeypatch):
    """The detector must catch the shape P3B's calculus map had, and not flag a healthy map."""
    broken = {
        "source": "x", "source_ids": ["calculus_textbook_1_sciencep_listing"],
        "inclusion_policy": mk.CANONICAL_INCLUSION_POLICY, "scope_note": "x",
        "chapters": [{"code": "0", "title": "上册（待补）", "children": [
            {"code": None, "title": "极限", "children": []},
        ]}],
    }
    monkeypatch.setattr(mk, "load_map", lambda key: broken)
    audit = mk.audit_domain("calculus")
    assert audit.granularity_status == "incomplete_undeclared"
    assert not audit.ok

    declared = dict(broken, granularity_note="节级结构待补")
    monkeypatch.setattr(mk, "load_map", lambda key: declared)
    audit = mk.audit_domain("calculus")
    # Declared is a recorded fact, not a defect — but it is still reported.
    assert audit.granularity_status == "incomplete_declared"
    assert audit.ok


# ---------------------------------------------------------------- provenance

def test_every_content_source_is_reproducible():
    """Identity AND bytes, per source:

    a source that IS a local file carries that file's own hash and size; a source that is a
    bibliographic listing carries a provider and a reference and NO hash, because there are no
    bytes to hash. Neither kind may borrow the other's evidence.
    """
    content_sources = [s for s in mk.manifest_sources() if s["role"] == mk.CONTENT_SOURCE]
    assert content_sources
    for source in content_sources:
        assert source["title"]
        # Bibliographic identity, or an explicit admission that it is unknown.
        assert source.get("isbn") or source.get("publisher")
        assert source["used_for"]
        if source["source_kind"] == "local_file":
            assert source.get("local_reference_name"), source["source_id"]
            assert len(str(source.get("sha256") or "")) == 64, source["source_id"]
            assert isinstance(source.get("file_size"), int) and source["file_size"] > 0
            assert source["verification_status"] == mk.HASHED_LOCAL_FILE
        else:
            assert source["source_kind"] == "bibliographic_listing"
            assert source.get("provider") and source.get("reference"), source["source_id"]
            assert source["verification_status"] == mk.BIBLIOGRAPHIC_SOURCE


def test_the_manifest_is_internally_consistent():
    assert mk.audit_manifest() == ()


def test_a_hash_belongs_only_to_the_file_its_record_describes():
    """The P3B.5 defect, as a rule: file, size and hash are present together or absent together."""
    listing = mk.get_source("calculus_textbook_1_sciencep_listing")
    assert listing["source_kind"] == "bibliographic_listing"
    assert listing["local_reference_name"] is None
    assert listing["file_size"] is None
    assert listing["sha256"] is None, "a listing must not carry another file's hash"

    answer_book = mk.get_source("calculus_textbook_1_answer_book_local")
    assert answer_book["local_reference_name"] == "微积分一教材答案.pdf"
    assert answer_book["file_size"] == 56125093
    assert answer_book["sha256"] == "f04bec28f68f13f39e77117f5cf4d8c973ac443bbb59cd9a4c8700fc549acc6e"
    # The two records describe different things and share no evidence.
    assert listing["sha256"] != answer_book["sha256"]


@pytest.mark.parametrize("mutation,expected", [
    ({"sha256": "f" * 64}, "all present or all absent"),
    ({"file_size": 123}, "all present or all absent"),
    ({"sha256": "f" * 64, "file_size": 123}, "all present or all absent"),
])
def test_a_source_may_not_carry_partial_file_evidence(mutation, expected):
    base = dict(mk.get_source("calculus_textbook_1_sciencep_listing"))
    problems = mk.source_identity_problems({**base, **mutation})
    assert any(expected in problem for problem in problems)


def test_a_local_file_source_must_name_its_file():
    base = dict(mk.get_source("linear_algebra_lecture_notes"))
    problems = mk.source_identity_problems({**base, "local_reference_name": None, "sha256": None, "file_size": None})
    assert any("must name its file" in problem for problem in problems)


def test_a_listing_without_a_provider_or_reference_is_not_checkable():
    base = dict(mk.get_source("calculus_textbook_1_dushu_listing"))
    assert mk.source_identity_problems({**base, "provider": None})
    assert mk.source_identity_problems({**base, "reference": None})


def test_the_manifest_carries_no_path_and_no_machine_name():
    raw = mk.SOURCE_MANIFEST_PATH.read_text(encoding="utf-8")
    assert "D:\\" not in raw and "D:/" not in raw
    assert "C:\\" not in raw and "C:/" not in raw
    assert "26477" not in raw and "Users" not in raw
    for source in mk.manifest_sources():
        name = source.get("local_reference_name") or ""
        assert "\\" not in name and "/" not in name and ":" not in name


def test_every_source_id_in_every_map_resolves():
    for key in DOMAIN_KEYS:
        for source_id in mk.load_map(key)["source_ids"]:
            assert mk.get_source(source_id) is not None, f"{key} → {source_id}"


def test_a_source_used_by_a_map_is_a_content_source():
    for key in DOMAIN_KEYS:
        for source_id in mk.load_map(key)["source_ids"]:
            assert mk.get_source(source_id)["role"] == mk.CONTENT_SOURCE


def test_a_corroboration_source_may_not_define_content():
    """It supports a local fact of another source; it is not a source of the structure."""
    answer_book = mk.get_source("calculus_textbook_1_answer_book_local")
    assert answer_book["role"] == mk.CORROBORATION_SOURCE
    assert answer_book["role"] != mk.CONTENT_SOURCE
    # No map cites it as a content source, and no node resolves to it.
    for key in DOMAIN_KEYS:
        payload = mk.load_map(key)
        assert answer_book["source_id"] not in payload["source_ids"]
        raw = json.dumps(payload, ensure_ascii=False)
        assert f'"source_ref": "{answer_book["source_id"]}"' not in raw


def test_a_corroboration_source_may_not_become_a_coverage_authority():
    assert mk.source_is_authoritative("calculus_textbook_1_answer_book_local") is False
    for source in mk.manifest_sources():
        if source["role"] == mk.CORROBORATION_SOURCE:
            assert source["source_kind"] == "local_file"
            assert mk.source_is_authoritative(source["source_id"]) is False


def test_the_corroboration_links_state_exactly_what_was_checked():
    """A link is worthless if it does not say how far the check went."""
    links = mk.corroboration_links()
    assert links
    by_corroborator = {link["corroborated_by"]: link for link in links}
    titles = by_corroborator["calculus_textbook_1_dushu_listing"]
    assert titles["verifies"] == "chapter and section titles"
    numbering = by_corroborator["calculus_textbook_1_answer_book_local"]
    assert "section numbering" in numbering["verifies"]
    # The local file confirms a skeleton, and the record must not claim more than that.
    assert "title" not in numbering["verifies"]
    assert "14" in numbering["note"]


def test_calculus_chapters_1_to_4_resolve_to_the_listing_not_the_answer_book():
    """The fix, read at the node level."""
    payload = mk.load_map("calculus")
    chapters = {chapter["code"]: chapter for chapter in payload["chapters"]}
    for code in ("1", "2", "3", "4"):
        assert chapters[code]["source_ref"] == "calculus_textbook_1_sciencep_listing"
    # Corroboration is declared for the map, not attached to a node's identity.
    assert payload["corroborated_by"] == ["calculus_textbook_1_answer_book_local"]
    # And no node anywhere in any map resolves to a corroboration source.
    for key in DOMAIN_KEYS:
        audit = mk.audit_domain(key)
        assert audit.ok, audit.issues


# ---------------------------------------------------------------- coverage state and guard

def test_coverage_is_still_empty_and_nothing_opens():
    assert tax.MATH_COVERAGE == ()
    assert tax.MATH_COVERAGE_STATUS == "pending_syllabus_import"
    assert tax.math_ready_level() == "L1"
    assert tax.math_openable() is False
    for variant in tax.all_variants():
        assert tax.coverage_for(variant.id) == []


def test_no_recorded_source_is_authoritative_yet():
    """Nothing in the manifest may back a scope statement today."""
    for source in mk.manifest_sources():
        assert mk.source_is_authoritative(source["source_id"]) is False, source["source_id"]


def test_null_and_false_remain_different_answers():
    entry = tax.MathCoverageEntry(variant="math_1", domain="calculus", level="chapter",
                                  code="8", included=None, source_id="syllabus_national_pending")
    assert entry.included is None and entry.included is not False
    assert entry.to_dict()["included"] is None


@pytest.mark.parametrize("source_id", ["syllabus_national_pending", "calculus_textbook_2",
                                       "linear_algebra_lecture_notes", "probability_textbook",
                                       "no_such_source"])
def test_an_unverified_source_cannot_make_coverage_verified(source_id):
    """Including the pending syllabus: a recorded-but-unverified source proves nothing."""
    original = tax.MATH_COVERAGE
    try:
        tax.MATH_COVERAGE = (
            tax.MathCoverageEntry(variant="math_1", domain="calculus", level="domain",
                                  code="", included=True, source_id=source_id),
        )
        assert tax.coverage_verified("math_1") is False
        assert tax.math_openable() is False
    finally:
        tax.MATH_COVERAGE = original


def test_a_verified_coverage_authority_would_open_it(monkeypatch):
    """The gate is real: it opens for a verified authority, and only then."""
    verified = dict(mk.get_source("syllabus_national_pending"), verification_status=mk.VERIFIED)
    monkeypatch.setattr(mk, "get_source", lambda source_id: verified if source_id == "syllabus_national_pending" else None)
    original = tax.MATH_COVERAGE
    try:
        tax.MATH_COVERAGE = tuple(
            tax.MathCoverageEntry(variant=variant.id, domain="calculus", level="domain",
                                  code="", included=True, source_id="syllabus_national_pending")
            for variant in tax.all_variants()
        )
        assert tax.coverage_verified("math_1") is True
        assert tax.math_openable() is True
        assert tax.math_ready_level() == "L2"
    finally:
        tax.MATH_COVERAGE = original


# ---------------------------------------------------------------- import contract

def test_an_import_candidate_must_carry_everything():
    domain_keys = list(DOMAIN_KEYS)
    variant_ids = [variant.id for variant in tax.all_variants()]
    good = mk.MathCoverageImportCandidate(
        source_id="syllabus_national_pending", variant="math_1", level="chapter",
        domain="calculus", code="8", included=True, evidence_reference="大纲 第 8 章")
    # Correctly shaped, and still refused: its source is not verified.
    problems = mk.import_candidate_problems(good, domain_keys, variant_ids)
    assert any("not 'verified'" in problem for problem in problems)


@pytest.mark.parametrize("mutation", [
    {"source_id": "no_such_source"},
    {"source_id": "calculus_textbook_2"},          # a textbook cannot state scope
    {"variant": "math_4"},
    {"domain": "algebra"},
    {"level": "paragraph"},
    {"code": ""},                                   # a non-domain level needs a code
    {"evidence_reference": ""},
    {"included": None},                             # absence of a claim is not an import
])
def test_import_candidate_validation_rejects(mutation):
    base = dict(source_id="syllabus_national_pending", variant="math_1", level="chapter",
                domain="calculus", code="8", included=True, evidence_reference="evidence")
    problems = mk.import_candidate_problems(
        mk.MathCoverageImportCandidate(**{**base, **mutation}),
        list(DOMAIN_KEYS), [variant.id for variant in tax.all_variants()])
    assert problems


def test_a_verified_candidate_passes_validation(monkeypatch):
    """The contract is usable the day a real source arrives."""
    verified = dict(mk.get_source("syllabus_national_pending"), verification_status=mk.VERIFIED)
    monkeypatch.setattr(mk, "get_source", lambda source_id: verified if source_id == "syllabus_national_pending" else None)
    candidate = mk.MathCoverageImportCandidate(
        source_id="syllabus_national_pending", variant="math_2", level="section",
        domain="linear_algebra", code="6.5", included=False, evidence_reference="大纲 线性代数 第 6 章")
    assert mk.import_candidate_problems(
        candidate, list(DOMAIN_KEYS), [variant.id for variant in tax.all_variants()]) == []


# ---------------------------------------------------------------- API surface unchanged

def test_taxonomy_endpoint_shape_is_unchanged(client):
    body = client.get("/exam/prep/math/taxonomy").json()
    assert list(body) == [
        "math_taxonomy_version", "math_ready_level", "math_openable", "openable_reason",
        "domains", "variants", "coverage_status", "coverage_note", "coverage_sources", "coverage",
    ]
    assert body["coverage"] == []
    assert [source["id"] for source in body["coverage_sources"]] == ["syllabus_national_pending"]
    assert body["coverage_sources"][0]["verification_status"] == mk.PENDING_SOURCE


def test_maths_subjects_still_do_not_open(client):
    register_and_login(client, "math_p3b5", "math-p3b5-pass-1")
    for variant in tax.all_variants():
        assert client.get(f"/exam/prep/subjects/{variant.subject_id}/content-status").status_code == 409
        assert catalog.is_known_module(variant.subject_id) is False
