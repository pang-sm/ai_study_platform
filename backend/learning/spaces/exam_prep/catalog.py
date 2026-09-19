"""Exam Prep catalog — CONFIG, not SQL (STEP7H4).

Exam Prep covers national standardized (全国统一命题) postgraduate entrance exam
subjects. This file is the product's whole exam taxonomy; it is versioned config so it
can be reviewed and diffed like code, and so no table exists for something the product
can express as a constant.

    ExamTrack   the learner's preparation direction / bundle
    ExamSubject an actual exam paper (全国统考科目)
    ExamModule  a part of a subject with its own teaching structure

Three separate concepts on purpose: a track is "how I am preparing", a subject is "what
is examined", a module is "how the subject is organised". Collapsing them into one enum
is what makes an 11408-sized design impossible to widen.

AVAILABILITY — the load-bearing rule of H4
------------------------------------------
``ACTIVE``          real, shipped content exists (questions, past papers, knowledge tree)
``FRAMEWORK_ONLY``  the direction is selectable and representable, and NOTHING is faked

Only CS408 is ACTIVE. Every other entry is a name, a category and an availability flag —
no chapters, no knowledge points, no questions, no generated placeholders. Adding real
content to a framework-only subject is a separate, content-bearing decision.

Institution-specific exams (院校自命题 / school exam codes / school syllabi / reference
books) are permanently OUT OF SCOPE and have no representation here.
"""
from __future__ import annotations

from dataclasses import dataclass, field

CATALOG_VERSION = "v2"

EXAM_TYPE_POSTGRADUATE = "postgraduate"

# Availability
ACTIVE = "active"
FRAMEWORK_ONLY = "framework_only"

# Categories (product-facing grouping; not an exam rule)
CATEGORY_PUBLIC = "public"            # 公共课
CATEGORY_PROFESSIONAL = "professional"  # 专业统考

NOT_AVAILABLE_REASON = "EXAM_CONTENT_NOT_AVAILABLE"


@dataclass(frozen=True)
class ExamModuleDefinition:
    id: str
    display_name: str


@dataclass(frozen=True)
class ExamSubjectDefinition:
    id: str
    display_name: str
    category: str
    availability: str
    description: str = ""
    # Track ids this subject is normally part of. INFORMATIONAL ONLY — it is not an exam
    # rule, and a learner's own selection is what defines their scope.
    suggested_tracks: tuple[str, ...] = ()
    modules: tuple[ExamModuleDefinition, ...] = field(default_factory=tuple)

    @property
    def is_active(self) -> bool:
        return self.availability == ACTIVE

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "display_name": self.display_name,
            "category": self.category,
            "availability": self.availability,
            # Capability flags are DERIVED FROM CONFIG, never from counting DB rows:
            # a product capability must not change because a table happens to be empty.
            "has_questions": self.is_active,
            "has_past_papers": self.is_active,
            "has_knowledge_tree": self.is_active,
            "description": self.description,
            "suggested_tracks": list(self.suggested_tracks),
            "modules": [{"id": m.id, "display_name": m.display_name} for m in self.modules],
        }


@dataclass(frozen=True)
class ExamTrackDefinition:
    id: str
    display_name: str
    exam_type: str
    availability: str
    description: str = ""
    # A DEFAULT, not a rule: real public-course bundles vary by degree type, institution
    # requirement and admissions year, so the learner's ``selected_subjects`` wins.
    subject_options: tuple[str, ...] = ()
    suggested_subjects: tuple[str, ...] = ()

    @property
    def is_active(self) -> bool:
        return self.availability == ACTIVE

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "display_name": self.display_name,
            "exam_type": self.exam_type,
            "availability": self.availability,
            "has_content": self.is_active,
            "description": self.description,
            "subject_options": list(self.subject_options),
            "suggested_subjects": list(self.suggested_subjects),
        }


# ---------------------------------------------------------------- CS 408 (ACTIVE)

CS408_TRACK = "cs_408"
CS408_SUBJECT = "cs_408"
CS408_MODULES = (
    "data_structure",
    "computer_organization",
    "operating_system",
    "computer_network",
)
CS408_MODULE_DISPLAY = {
    "data_structure": "数据结构",
    "computer_organization": "计算机组成原理",
    "operating_system": "操作系统",
    "computer_network": "计算机网络",
}
CS408_DISPLAY = "计算机学科专业基础 408"


# ---------------------------------------------------------------- subjects

EXAM_SUBJECTS: tuple[ExamSubjectDefinition, ...] = (
    ExamSubjectDefinition(
        id=CS408_SUBJECT,
        display_name=CS408_DISPLAY,
        category=CATEGORY_PROFESSIONAL,
        availability=ACTIVE,
        description="全国统考计算机学科专业基础综合（408）",
        suggested_tracks=(CS408_TRACK,),
        modules=tuple(ExamModuleDefinition(id=m, display_name=CS408_MODULE_DISPLAY[m])
                      for m in CS408_MODULES),
    ),
    # ---- 公共课：framework only ----
    ExamSubjectDefinition(id="politics", display_name="思想政治理论",
                          category=CATEGORY_PUBLIC, availability=FRAMEWORK_ONLY),
    ExamSubjectDefinition(id="english_1", display_name="英语（一）",
                          category=CATEGORY_PUBLIC, availability=FRAMEWORK_ONLY),
    ExamSubjectDefinition(id="english_2", display_name="英语（二）",
                          category=CATEGORY_PUBLIC, availability=FRAMEWORK_ONLY),
    ExamSubjectDefinition(id="math_1", display_name="数学（一）",
                          category=CATEGORY_PUBLIC, availability=FRAMEWORK_ONLY),
    ExamSubjectDefinition(id="math_2", display_name="数学（二）",
                          category=CATEGORY_PUBLIC, availability=FRAMEWORK_ONLY),
    ExamSubjectDefinition(id="math_3", display_name="数学（三）",
                          category=CATEGORY_PUBLIC, availability=FRAMEWORK_ONLY),
    # ---- 专业统考：framework only ----
    ExamSubjectDefinition(id="management_aptitude", display_name="管理类综合能力",
                          category=CATEGORY_PROFESSIONAL, availability=FRAMEWORK_ONLY),
    ExamSubjectDefinition(id="economics_joint_aptitude", display_name="经济类综合能力",
                          category=CATEGORY_PROFESSIONAL, availability=FRAMEWORK_ONLY),
    ExamSubjectDefinition(id="law_master_law", display_name="法律硕士（法学）全国统考科目",
                          category=CATEGORY_PROFESSIONAL, availability=FRAMEWORK_ONLY),
    ExamSubjectDefinition(id="law_master_non_law", display_name="法律硕士（非法学）全国统考科目",
                          category=CATEGORY_PROFESSIONAL, availability=FRAMEWORK_ONLY),
    ExamSubjectDefinition(id="education_basics", display_name="教育学专业基础",
                          category=CATEGORY_PROFESSIONAL, availability=FRAMEWORK_ONLY),
    ExamSubjectDefinition(id="psychology_basics", display_name="心理学专业基础",
                          category=CATEGORY_PROFESSIONAL, availability=FRAMEWORK_ONLY),
    ExamSubjectDefinition(id="history_basics", display_name="历史学专业基础",
                          category=CATEGORY_PROFESSIONAL, availability=FRAMEWORK_ONLY),
)


# ---------------------------------------------------------------- tracks
#
# ``suggested_subjects`` is EMPTY on purpose for every track except cs_408. There is no
# authoritative source in this repository for "which public courses a given direction
# requires" — that varies by degree type, institution requirement and year — so the
# catalog does not guess. The learner's ``selected_subjects`` is the real scope.

EXAM_TRACKS: tuple[ExamTrackDefinition, ...] = (
    ExamTrackDefinition(
        id=CS408_TRACK, display_name="计算机 408", exam_type=EXAM_TYPE_POSTGRADUATE,
        availability=ACTIVE,
        description="计算机学科专业基础综合（408）",
        subject_options=(CS408_SUBJECT,),
        suggested_subjects=(CS408_SUBJECT,),
    ),
    ExamTrackDefinition(id="management_joint", display_name="管理类联考",
                        exam_type=EXAM_TYPE_POSTGRADUATE, availability=FRAMEWORK_ONLY,
                        subject_options=("management_aptitude", "english_2")),
    ExamTrackDefinition(id="economics_joint", display_name="经济类联考",
                        exam_type=EXAM_TYPE_POSTGRADUATE, availability=FRAMEWORK_ONLY,
                        subject_options=("economics_joint_aptitude", "politics",
                                         "english_1", "math_3")),
    ExamTrackDefinition(id="law_jm_law", display_name="法律硕士（法学）",
                        exam_type=EXAM_TYPE_POSTGRADUATE, availability=FRAMEWORK_ONLY,
                        subject_options=("politics", "english_1", "law_master_law")),
    ExamTrackDefinition(id="law_jm_non_law", display_name="法律硕士（非法学）",
                        exam_type=EXAM_TYPE_POSTGRADUATE, availability=FRAMEWORK_ONLY,
                        subject_options=("politics", "english_1", "law_master_non_law")),
    ExamTrackDefinition(id="education", display_name="教育学",
                        exam_type=EXAM_TYPE_POSTGRADUATE, availability=FRAMEWORK_ONLY,
                        subject_options=("politics", "english_1", "education_basics")),
    ExamTrackDefinition(id="psychology", display_name="心理学",
                        exam_type=EXAM_TYPE_POSTGRADUATE, availability=FRAMEWORK_ONLY,
                        subject_options=("politics", "english_1", "psychology_basics")),
    ExamTrackDefinition(id="history", display_name="历史学",
                        exam_type=EXAM_TYPE_POSTGRADUATE, availability=FRAMEWORK_ONLY,
                        subject_options=("politics", "english_1", "history_basics")),
)


# ---------------------------------------------------------------- lookup

_SUBJECT_BY_ID = {s.id: s for s in EXAM_SUBJECTS}
_TRACK_BY_ID = {t.id: t for t in EXAM_TRACKS}


def get_subject(subject_id: str | None) -> ExamSubjectDefinition | None:
    return _SUBJECT_BY_ID.get((subject_id or "").strip())


def get_track(track_id: str | None) -> ExamTrackDefinition | None:
    return _TRACK_BY_ID.get((track_id or "").strip())


def all_subjects() -> list[ExamSubjectDefinition]:
    return list(EXAM_SUBJECTS)


def all_tracks() -> list[ExamTrackDefinition]:
    return list(EXAM_TRACKS)


def active_subjects() -> list[ExamSubjectDefinition]:
    return [s for s in EXAM_SUBJECTS if s.is_active]


def framework_only_subjects() -> list[ExamSubjectDefinition]:
    return [s for s in EXAM_SUBJECTS if not s.is_active]


def is_active_subject(subject_id: str | None) -> bool:
    subject = get_subject(subject_id)
    return bool(subject and subject.is_active)


def subject_supports_content(subject_id: str | None) -> bool:
    """Whether real learning content exists for this subject — the availability gate.

    Derived from CONFIG. A framework-only subject has no chapters, no knowledge points
    and no questions, and must never be presented as merely "empty".
    """
    return is_active_subject(subject_id)


# ---------------------------------------------------------------- CS408 module helpers

def is_known_module(module_key: str | None) -> bool:
    return (module_key or "").strip() in CS408_MODULES


def module_display(module_key: str | None) -> str:
    return CS408_MODULE_DISPLAY.get((module_key or "").strip(), (module_key or "").strip())
