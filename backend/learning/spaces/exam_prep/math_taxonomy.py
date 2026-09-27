"""考研数学 taxonomy — CONFIG, not SQL (EXAM_MATH P3B).

The maths exam is ONE subject with three papers. This module is the product's whole statement
about it, and it is versioned config so it can be reviewed and diffed like code — exactly as
``catalog.py`` is for the rest of the exam taxonomy.

    MathDomain        the three canonical parts of the maths exam
    MathExamVariant   数学（一）/（二）/（三） — a PAPER, i.e. a SCOPE over the domains
    MathCoverage      which domains (or chapters, or sections) a paper examines

THE ONE RULE THAT MATTERS
-------------------------
A domain exists ONCE. A paper never owns content; it only says what is in scope. So a knowledge
point is ``linear_algebra`` + its path, and the paper decides whether the learner needs it.
Switching 数学（一） → 数学（二） therefore changes the learner's target range and nothing else —
their knowledge, their progress and their records stay attached to the same canonical ids.
Nothing in this file may ever be written per-paper: no ``math_1_linear_algebra``.

WHY COVERAGE IS EMPTY
---------------------
``MATH_COVERAGE`` is deliberately EMPTY and every paper's range is therefore UNSTATED, not
unknown-but-guessed. Which chapters a paper examines is national syllabus data, and this project
has no authoritative source for it: 《全国硕士研究生招生考试数学考试大纲》 is a commercially
published book (高等教育出版社, ISBN 9787040546729), and every free copy reachable from the public
web is a training institution's transcription, which is not a source this product may treat as
truth. Writing the range from model memory would put an unverified exam rule in front of a
learner, so it is not written at all.

``included`` has three values and the third is not a soft ``false``:
    True   an authoritative source confirms the item IS in this paper's range
    False  an authoritative source confirms the item is NOT in this paper's range
    None   nobody has established it — the current state of everything here

Adding coverage is a CONTENT import (P3C): it means adding entries with a real
``MathCoverageSource``, not editing this file's structure.

The knowledge maps themselves live where every other knowledge map lives —
``backend/seed_data/knowledge_maps/<domain>.json`` — one per DOMAIN, never one per paper.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from learning.spaces.exam_prep import math_knowledge

MATH_TAXONOMY_VERSION = "v1"

# Where the canonical knowledge maps are seeded. Same directory and same chapter→section→leaf
# format as every other knowledge map in this project; only the key is a domain rather than a
# course, which is what makes the maths structure reusable across the three papers. The directory
# is owned by `math_knowledge`, which is also where the structural audit lives.
KNOWLEDGE_MAP_DIR = math_knowledge.KNOWLEDGE_MAP_DIR

# The rule the maps are built under: a map contains what its source contains, in full. Exam scope
# never adds or removes a node. Recorded here as a value so a reader of the taxonomy — and a test
# — can see the policy the product claims, and the answer to the question it implies.
CANONICAL_INCLUSION_POLICY = math_knowledge.CANONICAL_INCLUSION_POLICY

# Whether what counts as canonical content is decided by an exam's scope. It is not, and the shape
# of the code is the proof: nothing that reads a map consults coverage.
CANONICAL_CONTENT_DEPENDS_ON_EXAM_SCOPE = False

# Verification state of a coverage claim's source.
VERIFIED = "verified"
PENDING_SOURCE = "pending_source"

# Whether a domain's knowledge map has been built.
MAP_AVAILABLE = "available"
MAP_PENDING = "pending"


@dataclass(frozen=True)
class MathDomainDefinition:
    """One canonical part of the maths exam. Exactly three exist, and each exists once."""

    key: str
    display_name: str
    order: int
    # The knowledge map key: ``seed_data/knowledge_maps/<key>.json``.
    knowledge_map_id: str
    source: str
    source_reference: str

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "display_name": self.display_name,
            "order": self.order,
            "knowledge_map_id": self.knowledge_map_id,
            "status": MAP_AVAILABLE if knowledge_map_available(self) else MAP_PENDING,
            "source": self.source,
            "source_reference": self.source_reference,
        }


@dataclass(frozen=True)
class MathExamVariantDefinition:
    """A paper. It decides SCOPE; it owns no content and has no knowledge map of its own."""

    id: str
    display_name: str
    # The subject id this paper is, in the exam catalogue.
    subject_id: str
    order: int

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "display_name": self.display_name,
            "subject_id": self.subject_id,
            "order": self.order,
        }


@dataclass(frozen=True)
class MathCoverageSource:
    """Where a coverage claim came from. A claim without one of these cannot be verified."""

    id: str
    name: str
    kind: str
    reference: str
    verification_status: str
    note: str

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "kind": self.kind,
            "reference": self.reference,
            "verification_status": self.verification_status,
            "note": self.note,
        }


@dataclass(frozen=True)
class MathCoverageEntry:
    """One statement that a paper does or does not examine one canonical item.

    ``included`` is True / False / None. ``None`` means the question is open, which is different
    from a confirmed "not in scope" — a surface must be able to tell those apart, and must never
    render an open question as a settled answer.
    """

    variant: str
    domain: str
    level: str  # "domain" | "chapter" | "section"
    code: str
    included: bool | None
    source_id: str

    def to_dict(self) -> dict:
        return {
            "variant": self.variant,
            "domain": self.domain,
            "level": self.level,
            "code": self.code,
            "included": self.included,
            "source_id": self.source_id,
        }


# ---------------------------------------------------------------- domains

MATH_DOMAINS: tuple[MathDomainDefinition, ...] = (
    MathDomainDefinition(
        key="calculus",
        display_name="高等数学",
        order=1,
        knowledge_map_id="calculus",
        source="《微积分 I》《微积分 II》(第三版) 南京大学·大学数学系列，科学出版社",
        source_reference="第 1–4 章标题取自《微积分 I（第三版）》的书目目录（科学出版社旗舰店，并经读书网同一书目复核）；第 5–10 章标题逐条取自本地《微积分 II(第三版)》目录。",
    ),
    MathDomainDefinition(
        key="linear_algebra",
        display_name="线性代数",
        order=2,
        knowledge_map_id="linear_algebra",
        source="《线性代数讲义》南京大学·大学数学系列，科学出版社",
        source_reference="第 1–7 章逐条取自该书目录。",
    ),
    MathDomainDefinition(
        key="probability_statistics",
        display_name="概率论与数理统计",
        order=3,
        knowledge_map_id="probability_statistics",
        source="《概率论与数理统计》傅冬生/赵进/谢兆茹/刘荣丽 编，科学出版社",
        source_reference="第一至第八章的章、节、条目层级取自该书目录。",
    ),
)


# ---------------------------------------------------------------- papers

MATH_VARIANTS: tuple[MathExamVariantDefinition, ...] = (
    MathExamVariantDefinition(id="math_1", display_name="数学（一）", subject_id="math_1", order=1),
    MathExamVariantDefinition(id="math_2", display_name="数学（二）", subject_id="math_2", order=2),
    MathExamVariantDefinition(id="math_3", display_name="数学（三）", subject_id="math_3", order=3),
)


# ---------------------------------------------------------------- coverage sources

def _coverage_sources_from_manifest() -> tuple[MathCoverageSource, ...]:
    """The sources that may back a coverage claim, read from the single source registry.

    `seed_data/math_sources.json` holds every source either kind of document was built from — the
    textbooks behind the knowledge maps AND the syllabus that would back coverage. This view is
    the coverage half of it: only a source whose role is `coverage_authority` can state an exam
    range, so a textbook can never be pressed into answering a scope question.
    """
    return tuple(
        MathCoverageSource(
            id=source["source_id"],
            name=str(source.get("title") or source["source_id"]),
            kind=str(source.get("source_kind") or ""),
            reference=str(source.get("publisher") or "")
            + (f"（ISBN {source['isbn']}）" if source.get("isbn") else ""),
            verification_status=str(source.get("verification_status") or math_knowledge.PENDING_SOURCE),
            note=str(source.get("limitations") or ""),
        )
        for source in math_knowledge.manifest_sources()
        if source.get("role") == math_knowledge.COVERAGE_AUTHORITY
    )


MATH_COVERAGE_SOURCES: tuple[MathCoverageSource, ...] = _coverage_sources_from_manifest()

# No coverage claims exist. See the module docstring: writing them from anything but an
# authoritative source would put an unverified exam rule in front of a learner.
MATH_COVERAGE: tuple[MathCoverageEntry, ...] = ()

MATH_COVERAGE_STATUS = "pending_syllabus_import"

MATH_COVERAGE_NOTE = "考试范围待正式导入，以当年全国硕士研究生招生考试大纲为准。"


# ---------------------------------------------------------------- lookup

_DOMAIN_BY_KEY = {domain.key: domain for domain in MATH_DOMAINS}
_VARIANT_BY_ID = {variant.id: variant for variant in MATH_VARIANTS}


def get_domain(domain_key: str | None) -> MathDomainDefinition | None:
    return _DOMAIN_BY_KEY.get((domain_key or "").strip())


def get_variant(variant_id: str | None) -> MathExamVariantDefinition | None:
    return _VARIANT_BY_ID.get((variant_id or "").strip())


def all_domains() -> list[MathDomainDefinition]:
    return sorted(MATH_DOMAINS, key=lambda domain: domain.order)


def all_variants() -> list[MathExamVariantDefinition]:
    return sorted(MATH_VARIANTS, key=lambda variant: variant.order)


def knowledge_map_path(domain: MathDomainDefinition) -> Path:
    return KNOWLEDGE_MAP_DIR / f"{domain.knowledge_map_id}.json"


def knowledge_map_available(domain: MathDomainDefinition) -> bool:
    """Whether the canonical knowledge map for this domain has been built.

    Read from the filesystem rather than declared, so a map that is added or removed cannot leave
    this module claiming a structure the product cannot actually read.
    """
    return knowledge_map_path(domain).is_file()


def coverage_for(variant_id: str) -> list[MathCoverageEntry]:
    """The stated range of one paper — empty until an authoritative source has been imported."""
    return [entry for entry in MATH_COVERAGE if entry.variant == variant_id]


def coverage_verified(variant_id: str) -> bool:
    """Whether ANY of this paper's range has been established from an authoritative source.

    The guard is `math_knowledge.source_is_authoritative`, and it is deliberately narrow: a source
    must be a coverage authority AND be VERIFIED. A textbook, a bibliographic listing, a pending
    record, or anything training-institution- or model-generated cannot make a scope statement, so
    a claim citing one leaves this False however it is written.
    """
    return any(entry.included is not None and math_knowledge.source_is_authoritative(entry.source_id)
               for entry in coverage_for(variant_id))


def math_openable() -> bool:
    """The L2 gate: every domain has a knowledge map AND every paper has verified coverage.

    Both halves are required, so a knowledge structure with no established exam range does not
    open the subject — a learner would be shown a body of content with no way to know which part
    of it their paper examines.
    """
    if not all(knowledge_map_available(domain) for domain in all_domains()):
        return False
    return all(coverage_verified(variant.id) for variant in all_variants())


def math_ready_level() -> str:
    """The product-side readiness of the maths space, derived rather than declared."""
    if math_openable():
        return "L2"
    if all(knowledge_map_available(domain) for domain in all_domains()):
        return "L1"
    return "L0"


def openable_reason() -> str:
    """Why the maths space is or is not open, in one sentence for a product surface."""
    if math_openable():
        return "知识结构与考试范围均已具备，数学学习入口可以开放。"
    missing_maps = [domain.display_name for domain in all_domains() if not knowledge_map_available(domain)]
    if missing_maps:
        return f"知识体系尚未建立完整（缺 {', '.join(missing_maps)}），数学学习入口暂不开放。"
    return "知识体系已建立，但数学（一）/（二）/（三）的考试范围尚未由权威大纲导入，数学学习入口暂不开放。"


def taxonomy_payload() -> dict:
    """The whole maths taxonomy, as the product reads it."""
    return {
        "math_taxonomy_version": MATH_TAXONOMY_VERSION,
        "math_ready_level": math_ready_level(),
        "math_openable": math_openable(),
        "openable_reason": openable_reason(),
        "domains": [domain.to_dict() for domain in all_domains()],
        "variants": [variant.to_dict() for variant in all_variants()],
        "coverage_status": MATH_COVERAGE_STATUS,
        "coverage_note": MATH_COVERAGE_NOTE,
        "coverage_sources": [source.to_dict() for source in MATH_COVERAGE_SOURCES],
        "coverage": [entry.to_dict() for entry in MATH_COVERAGE],
    }
