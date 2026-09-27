"""考研数学 canonical knowledge maps — the boundary rule, the source registry, and the audit.

TWO QUESTIONS, TWO DOCUMENTS
----------------------------
A canonical knowledge map answers "what mathematics do we model for this domain?". Coverage
answers "which of it does 数学（一）/（二）/（三） examine?". They are separate documents on
purpose, and the separation is load-bearing:

  * A map is built from a **source**, and it contains what that source contains — in full.
  * Coverage is built from an **authority** (the national syllabus), and it is currently empty.

So nothing is ever removed from a map because an exam may not test it. If `included` were allowed
to decide what exists, then 数学（二） → 数学（一） would change the learner's content, three copies
of every domain would appear sooner or later, and a future syllabus revision would silently delete
history. `CANONICAL_INCLUSION_POLICY` below is that rule as a value, and a test asserts the maps
obey it.

WHY THE SOURCES ARE A MANIFEST AND NOT THE FILES
------------------------------------------------
The knowledge maps were read from course textbooks that live on one machine. Archiving them is not
allowed (copyright), and citing a local path is not reproducible. So `seed_data/math_sources.json`
records identity — title, authors, publisher, edition, ISBN where known — plus the file's size and
SHA-256, which is what lets a later reader confirm that a file they hold is the same one this map
was built from. No path, no machine name, no user name is recorded.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

# Where the canonical knowledge maps and the source manifest live. Same directory and same
# chapter→section→leaf format as every other knowledge map in this project.
SEED_DATA_DIR = Path(__file__).resolve().parents[3] / "seed_data"
KNOWLEDGE_MAP_DIR = SEED_DATA_DIR / "knowledge_maps"
SOURCE_MANIFEST_PATH = SEED_DATA_DIR / "math_sources.json"

MANIFEST_VERSION = "v1"

# ---------------------------------------------------------------- the boundary rule

# The only inclusion policy the maths maps use: everything the cited source presents as its own
# course content, in full. Optional/advanced sections marked by the source are INCLUDED — the
# source's own marking is not an exam judgement, and even if it were, it would belong to coverage.
SOURCE_CONTENT_COMPLETE = "source_content_complete"

CANONICAL_INCLUSION_POLICY = SOURCE_CONTENT_COMPLETE

INCLUSION_POLICIES = (SOURCE_CONTENT_COMPLETE,)

# A map states the policy it was built under, so a reader can tell which rule produced it.
REQUIRED_MAP_METADATA = ("source", "source_ids", "inclusion_policy", "scope_note")

# ---------------------------------------------------------------- source roles

# A role says what a source may DEFINE, not merely what it is. Three, and the boundaries between
# them are the point:
#
#   content_source      may define canonical knowledge content
#   coverage_authority  may define an exam's scope
#   corroboration_source may support a LOCAL FACT of another source — a section numbering skeleton,
#                       say — and may do nothing else: it cannot define content, and it cannot
#                       define scope. A file that confirms a shape is not a source of the shape.
CONTENT_SOURCE = "content_source"
COVERAGE_AUTHORITY = "coverage_authority"
CORROBORATION_SOURCE = "corroboration_source"

SOURCE_ROLES = (CONTENT_SOURCE, COVERAGE_AUTHORITY, CORROBORATION_SOURCE)

# Verification states a source can be in.
#
#   hashed_local_file     the source IS a local file, and the recorded hash belongs to it
#   bibliographic_source  identity comes from a published listing; no bytes exist
#   pending_source        nothing usable yet
#   verified              fully checked against its content (nothing is here yet)
#
# There is deliberately no `corroborated` state. It would have to mean "part of this is confirmed
# and part is not", which is a property of a CLAIM rather than of a source, and putting it here is
# exactly how a single-source fact ends up reading as a checked one. What was corroborated, and
# how far, is stated in `corroboration` and in the manifest's `corroborations` links.
HASHED_LOCAL_FILE = "hashed_local_file"
BIBLIOGRAPHIC_SOURCE = "bibliographic_source"
PENDING_SOURCE = "pending_source"
VERIFIED = "verified"

# A coverage claim may only become authoritative when its source is VERIFIED. These are the states
# that must never do it — the first three are recorded states, the last three are the kinds of
# source the brief forbids as canonical truth.
NON_AUTHORITATIVE_VERIFICATION = (
    PENDING_SOURCE,
    HASHED_LOCAL_FILE,      # a textbook proves content, not exam scope
    BIBLIOGRAPHIC_SOURCE,   # a listing proves a title, not a syllabus
    "unverified",
    "training_institution",
    "model_generated",
)

# ---------------------------------------------------------------- loading


def load_manifest() -> dict:
    return json.loads(SOURCE_MANIFEST_PATH.read_text(encoding="utf-8"))


def manifest_sources() -> list[dict]:
    return list(load_manifest().get("sources") or [])


def sources_by_id() -> dict[str, dict]:
    return {source["source_id"]: source for source in manifest_sources()}


def get_source(source_id: str | None) -> dict | None:
    return sources_by_id().get((source_id or "").strip())


def coverage_authority_ids() -> list[str]:
    return [source["source_id"] for source in manifest_sources()
            if source.get("role") == COVERAGE_AUTHORITY]


def corroboration_links() -> list[dict]:
    return list(load_manifest().get("corroborations") or [])


def content_source_ids() -> list[str]:
    return [source["source_id"] for source in manifest_sources()
            if source.get("role") == CONTENT_SOURCE]


# ---------------------------------------------------------------- identity audit

_BARE_FILENAME_FORBIDDEN = ("\\", "/", ":")


def source_identity_problems(source: dict) -> list[str]:
    """Whether a source record's identity is internally consistent.

    The rule this exists for: **a hash belongs to the file its own record describes.** A record
    that cites a bibliographic listing must not carry the SHA-256 of some other file — that is how
    a listing inherits the credibility of a file it never came from. So the file reference, the
    size and the hash are all present together or all absent together, with nothing in between.
    """
    source_id = str(source.get("source_id") or "?")
    problems: list[str] = []

    if source.get("role") not in SOURCE_ROLES:
        problems.append(f"{source_id}: unknown role {source.get('role')!r}")

    name = source.get("local_reference_name")
    digest = source.get("sha256")
    size = source.get("file_size")
    has_file, has_hash, has_size = bool(name), bool(digest), size is not None

    if not (has_file == has_hash == has_size):
        problems.append(
            f"{source_id}: local_reference_name / sha256 / file_size must be all present or all "
            f"absent (file={has_file}, hash={has_hash}, size={has_size})")
    if has_hash and len(str(digest)) != 64:
        problems.append(f"{source_id}: sha256 is not a sha256 digest")
    if has_size and (not isinstance(size, int) or isinstance(size, bool) or size <= 0):
        problems.append(f"{source_id}: file_size must be a positive integer")
    if has_file:
        if any(char in str(name) for char in _BARE_FILENAME_FORBIDDEN):
            problems.append(f"{source_id}: local_reference_name must be a bare filename, not a path")

    kind = str(source.get("source_kind") or "")
    if kind == "bibliographic_listing":
        # A listing without a provider and a reference is not checkable by anyone.
        if not str(source.get("provider") or "").strip():
            problems.append(f"{source_id}: a bibliographic listing needs a provider")
        if not str(source.get("reference") or "").strip():
            problems.append(f"{source_id}: a bibliographic listing needs a reference")
        if source.get("role") == CORROBORATION_SOURCE:
            problems.append(f"{source_id}: a listing that supplied titles is not a corroboration source")
    if kind == "local_file" and not has_file:
        problems.append(f"{source_id}: a local_file source must name its file")

    if source.get("verification_status") not in (HASHED_LOCAL_FILE, BIBLIOGRAPHIC_SOURCE,
                                                 PENDING_SOURCE, VERIFIED):
        problems.append(f"{source_id}: unknown verification_status {source.get('verification_status')!r}")

    return problems


def audit_manifest() -> tuple[str, ...]:
    """Every structural problem in the source registry. Empty means it is internally consistent."""
    issues: list[str] = []
    sources = sources_by_id()
    for source in manifest_sources():
        issues.extend(source_identity_problems(source))

    for link in corroboration_links():
        subject = str(link.get("subject_source_id") or "")
        corroborator = str(link.get("corroborated_by") or "")
        if not subject or not corroborator or not str(link.get("verifies") or "").strip():
            issues.append("a corroboration link is missing subject_source_id / corroborated_by / verifies")
            continue
        if subject not in sources:
            issues.append(f"corroboration subject {subject!r} does not resolve")
        if corroborator not in sources:
            issues.append(f"corroboration source {corroborator!r} does not resolve")
        if subject == corroborator:
            issues.append(f"{subject!r} cannot corroborate itself")

    raw = SOURCE_MANIFEST_PATH.read_text(encoding="utf-8")
    for forbidden in ("D:\\", "D:/", "C:\\", "C:/", "Users\\", "Users/"):
        if forbidden in raw:
            issues.append(f"the manifest contains what looks like a path: {forbidden}")
    return tuple(issues)


def sources_corroborating(subject_source_id: str) -> list[str]:
    """Which sources back a stated fact of this one, and what each of them supports."""
    return [link["corroborated_by"] for link in corroboration_links()
            if link.get("subject_source_id") == subject_source_id]


def corroboration_verifies(subject_source_id: str, corroborator: str) -> str | None:
    for link in corroboration_links():
        if link.get("subject_source_id") == subject_source_id and link.get("corroborated_by") == corroborator:
            return str(link.get("verifies") or "")
    return None


def load_map(domain_key: str) -> dict:
    """The raw knowledge map for a domain. Raises if it is absent — a missing map is a bug."""
    path = KNOWLEDGE_MAP_DIR / f"{domain_key}.json"
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------- structural audit

CHAPTER = 1
SECTION = 2
LEAF = 3

# An id that names a paper. A canonical knowledge id must never look like one.
_VARIANT_PREFIX = re.compile(r"math_?[123]")


@dataclass(frozen=True)
class MathKnowledgeAudit:
    """What the audit found for one domain. Every count is measured, never declared."""

    domain: str
    chapters: int = 0
    sections: int = 0
    leaves: int = 0
    max_depth: int = 0
    min_depth: int = 0
    node_count: int = 0
    duplicate_count: int = 0
    invalid_parent_count: int = 0
    cycle_count: int = 0
    empty_name_count: int = 0
    duplicate_sibling_count: int = 0
    variant_prefixed_count: int = 0
    unresolved_source_refs: tuple[str, ...] = ()
    unresolved_source_ids: tuple[str, ...] = ()
    declaration_issues: tuple[str, ...] = ()
    granularity_status: str = "unknown"
    issues: tuple[str, ...] = field(default_factory=tuple)

    @property
    def ok(self) -> bool:
        return not self.issues

    def to_dict(self) -> dict:
        return {
            "domain": self.domain,
            "chapters": self.chapters,
            "sections": self.sections,
            "leaves": self.leaves,
            "node_count": self.node_count,
            "max_depth": self.max_depth,
            "min_depth": self.min_depth,
            "duplicate_count": self.duplicate_count,
            "invalid_parent_count": self.invalid_parent_count,
            "cycle_count": self.cycle_count,
            "empty_name_count": self.empty_name_count,
            "duplicate_sibling_count": self.duplicate_sibling_count,
            "variant_prefixed_count": self.variant_prefixed_count,
            "unresolved_source_refs": list(self.unresolved_source_refs),
            "unresolved_source_ids": list(self.unresolved_source_ids),
            "granularity_status": self.granularity_status,
            "issues": list(self.issues),
        }


def audit_domain(domain_key: str) -> MathKnowledgeAudit:
    """Walk one map and check every structural rule the maps must satisfy.

    The rules: ids unique, names non-empty and unique among siblings, no paper-named id, no
    cycles, depth within chapter→section→leaf, and every source reference resolvable.
    """
    payload = load_map(domain_key)
    chapters = payload.get("chapters") or []
    known_sources = sources_by_id()

    issues: list[str] = []
    declaration_issues: list[str] = []
    for key in REQUIRED_MAP_METADATA:
        if not payload.get(key):
            declaration_issues.append(f"missing map metadata: {key}")
    policy = payload.get("inclusion_policy")
    if policy and policy not in INCLUSION_POLICIES:
        declaration_issues.append(f"unknown inclusion_policy: {policy}")

    source_ids = [str(entry).strip() for entry in (payload.get("source_ids") or []) if str(entry).strip()]
    unresolved_source_ids = tuple(s for s in source_ids if s not in known_sources)
    if unresolved_source_ids:
        declaration_issues.append(f"unresolved source_ids: {', '.join(unresolved_source_ids)}")
    # Only a content source may define content. A corroborating file cited here would be a claim
    # that it supplied the structure, which is precisely what it did not do.
    for source_id in source_ids:
        source = known_sources.get(source_id)
        if source is not None and source.get("role") != CONTENT_SOURCE:
            declaration_issues.append(
                f"source_ids cites {source_id!r}, whose role is {source.get('role')!r}")

    # Corroboration is a statement about a SOURCE, so it is declared at map level and resolved
    # here; it never becomes the canonical source of a node.
    corroborated_by = [str(entry).strip() for entry in (payload.get("corroborated_by") or [])]
    for source_id in corroborated_by:
        source = known_sources.get(source_id)
        if source is None:
            declaration_issues.append(f"corroborated_by cites unknown source {source_id!r}")
        elif source.get("role") != CORROBORATION_SOURCE:
            declaration_issues.append(
                f"corroborated_by cites {source_id!r}, whose role is {source.get('role')!r}")

    default_ref = source_ids[0] if source_ids else ""
    unresolved_refs: list[str] = []

    seen_ids: set[str] = set()
    duplicates = 0
    empty_names = 0
    duplicate_siblings = 0
    variant_prefixed = 0
    invalid_parents = 0
    cycles = 0
    counts = {CHAPTER: 0, SECTION: 0, LEAF: 0}
    depths: list[int] = []
    node_count = 0

    def walk(nodes: list, depth: int, path: str, ancestor_ids: frozenset[str]) -> None:
        nonlocal duplicates, empty_names, duplicate_siblings, variant_prefixed
        nonlocal invalid_parents, cycles, node_count
        sibling_titles: set[str] = set()
        for index, node in enumerate(nodes, start=1):
            node_count += 1
            child_path = f"{path}.{index}"
            code = str(node.get("code") or "").strip()
            title = str(node.get("title") or "").strip()
            identifier = code or f"_leaf:{child_path}"

            if not title:
                empty_names += 1
                issues.append(f"{domain_key}:{child_path} has an empty title")
            if title and title in sibling_titles:
                duplicate_siblings += 1
                issues.append(f"{domain_key}:{child_path} repeats a sibling title {title!r}")
            sibling_titles.add(title)

            if identifier in seen_ids:
                duplicates += 1
                issues.append(f"{domain_key}:{child_path} repeats id {identifier!r}")
            seen_ids.add(identifier)

            if _VARIANT_PREFIX.search(identifier):
                variant_prefixed += 1
                issues.append(f"{domain_key}:{child_path} id {identifier!r} names an exam paper")

            if identifier in ancestor_ids:
                cycles += 1
                issues.append(f"{domain_key}:{child_path} revisits an ancestor id {identifier!r}")

            if depth > LEAF:
                invalid_parents += 1
                issues.append(f"{domain_key}:{child_path} is deeper than chapter→section→leaf")

            ref = str(node.get("source_ref") or default_ref).strip()
            if ref and ref not in known_sources:
                if ref not in unresolved_refs:
                    unresolved_refs.append(ref)
                    issues.append(f"{domain_key}:{child_path} cites unknown source {ref!r}")
            elif ref:
                # A node's canonical source must be able to define content. A corroborating file is
                # not one, so a node pointing at it would be claiming support it does not have.
                role = known_sources[ref].get("role")
                if role != CONTENT_SOURCE:
                    issues.append(
                        f"{domain_key}:{child_path} resolves to {ref!r}, whose role is {role!r}")

            children = node.get("children") or []
            if depth in counts:
                counts[depth] += 1
            if not children:
                depths.append(depth)
            walk(children, depth + 1, child_path, ancestor_ids | {identifier})

    walk(chapters, CHAPTER, "", frozenset())

    granularity = _granularity_status(domain_key, chapters, payload)
    # A DECLARED gap is a recorded fact, not a defect — it is reported so nobody mistakes the map
    # for a complete one, but it does not make the map invalid. An UNDECLARED gap is a finding.
    if granularity == "incomplete_undeclared":
        issues.append(f"{domain_key}: granularity_status={granularity}")

    return MathKnowledgeAudit(
        domain=domain_key,
        chapters=counts[CHAPTER],
        sections=counts[SECTION],
        leaves=counts[LEAF],
        max_depth=max(depths) if depths else 0,
        min_depth=min(depths) if depths else 0,
        node_count=node_count,
        duplicate_count=duplicates,
        invalid_parent_count=invalid_parents,
        cycle_count=cycles,
        empty_name_count=empty_names,
        duplicate_sibling_count=duplicate_siblings,
        variant_prefixed_count=variant_prefixed,
        unresolved_source_refs=tuple(unresolved_refs),
        unresolved_source_ids=unresolved_source_ids,
        declaration_issues=tuple(declaration_issues),
        granularity_status=granularity,
        issues=tuple(declaration_issues) + tuple(issues),
    )


def _granularity_status(domain_key: str, chapters: list, payload: dict) -> str:
    """Whether every chapter reaches section level.

    A section does not need children of its own: many sources present a section as one topic, and
    that is complete, not thin. What makes a chapter INCOMPLETE is having no sections at all, or
    having children that are topics wearing a section's place — which shows up as a child with no
    code, because a real section in these sources is always numbered.

    Read from the STRUCTURE rather than from the metadata, so a map cannot claim completeness the
    tree does not have.
    """
    for chapter in chapters:
        children = chapter.get("children") or []
        if not children:
            return _declared(payload, "incomplete")
        if any(not str(child.get("code") or "").strip() for child in children):
            return _declared(payload, "incomplete")
    return "complete"


def _declared(payload: dict, status: str) -> str:
    """A map that knows it is incomplete states so; one that does not is a finding."""
    return f"{status}_declared" if payload.get("granularity_note") else f"{status}_undeclared"


def audit_all(domain_keys: list[str]) -> list[MathKnowledgeAudit]:
    return [audit_domain(key) for key in domain_keys]


# ---------------------------------------------------------------- coverage import contract

@dataclass(frozen=True)
class MathCoverageImportCandidate:
    """What a future official-syllabus import must supply for ONE claim.

    Nothing imports without all of this, and nothing imports from a source that is not VERIFIED —
    see `import_candidate_problems`.
    """

    source_id: str
    variant: str
    level: str
    domain: str
    code: str
    included: bool
    evidence_reference: str

    def to_dict(self) -> dict:
        return {
            "source_id": self.source_id,
            "variant": self.variant,
            "level": self.level,
            "domain": self.domain,
            "code": self.code,
            "included": self.included,
            "evidence_reference": self.evidence_reference,
        }


IMPORT_LEVELS = ("domain", "chapter", "section")


def import_candidate_problems(candidate: MathCoverageImportCandidate,
                              domain_keys: list[str],
                              variant_ids: list[str]) -> list[str]:
    """Everything wrong with one proposed coverage claim. Empty means it may be imported.

    The source rule is the important one: `included` may only be **either** value when the claim's
    source is VERIFIED. A textbook, a listing, a pending record, or anything model-generated
    cannot make an exam-scope statement, so a candidate citing one is rejected outright rather
    than imported as a weak claim.
    """
    problems: list[str] = []
    source = get_source(candidate.source_id)
    if source is None:
        problems.append(f"unknown source_id: {candidate.source_id!r}")
    else:
        if source.get("role") != COVERAGE_AUTHORITY:
            problems.append(f"source {candidate.source_id!r} is not a coverage authority")
        status = str(source.get("verification_status") or "")
        if status != VERIFIED:
            problems.append(
                f"source {candidate.source_id!r} is {status!r}, not {VERIFIED!r} — "
                "an unverified source may not state exam scope")
    if candidate.variant not in variant_ids:
        problems.append(f"unknown variant: {candidate.variant!r}")
    if candidate.domain not in domain_keys:
        problems.append(f"unknown domain: {candidate.domain!r}")
    if candidate.level not in IMPORT_LEVELS:
        problems.append(f"unknown level: {candidate.level!r}")
    if not str(candidate.code or "").strip() and candidate.level != "domain":
        problems.append(f"level {candidate.level!r} requires a code")
    if not str(candidate.evidence_reference or "").strip():
        problems.append("missing evidence_reference")
    if not isinstance(candidate.included, bool):
        problems.append("included must be true or false — None is the ABSENCE of a claim, not one")
    return problems


def source_is_authoritative(source_id: str | None) -> bool:
    """Whether a source may back a coverage verdict at all."""
    source = get_source(source_id)
    if source is None:
        return False
    if source.get("role") != COVERAGE_AUTHORITY:
        return False
    return str(source.get("verification_status") or "") not in NON_AUTHORITATIVE_VERIFICATION
