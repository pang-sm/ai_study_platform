"""What a learner reads when they study ONE knowledge point of their own structure.

WHY THIS IS A SEPARATE SURFACE FROM THE STRUCTURE
-------------------------------------------------
The knowledge structure answers "which points exist". This answers "explain this one". They
have different lifetimes: the structure is regenerated in versions and confirmed, while an
explanation is bought once and read many times, and the two must not be coupled — a learner
changing their mind about the structure must not silently discard the explanations, and
reading an explanation must not move any progress state.

WHERE THE GROUNDING COMES FROM, AND WHY IT IS DECIDED HERE
----------------------------------------------------------
Two structures can be built the same way but mean different things:

    selected_materials  the tree was organized FROM the learner's own files, so those files
                        are the honest place to look for this point's passage
    ai_generated        the tree came from the model; the learner's library is not its source

So a `selected_materials` structure grounds in its own recorded ``source_file_ids``, while an
`ai_generated` structure grounds in the course library — which is what makes a learner who
generated a structure first and uploaded their textbook afterwards get their textbook cited.

The structure is NEVER rewritten by this module. Grounding and structure are different
questions, and answering one must not change the other.

WHAT A LEARNER NEVER SEES
-------------------------
No model name, no retrieval log, no chunk count, no similarity score, no "confidence". The
citations are the FILE and the PASSAGE — something the learner can open and check — and
nothing else. An explanation with no grounding carries no citations rather than an empty
citations block.
"""
from __future__ import annotations

import json

from .context import course_identity_forms, normalize_course_id

GROUNDING_SELECTED_MATERIALS = "selected_materials"
GROUNDING_AI_GENERATED = "ai_generated"
GROUNDING_NONE = "none"

CAPABILITY = "question.explain"

# Above the default chat ceiling, and set by the same measurement the structure generator uses:
# a thinking model spends part of the budget on its own reasoning, so a budget that looks generous
# for the visible answer is not. At 1800 the first production explanation came back cut off
# mid-sentence (704 characters, ending inside a clause), which is worse than a shorter answer that
# finished — the learner cannot tell where the explanation stopped and the topic began.
OUTPUT_TOKEN_BUDGET = 3000
MAX_GROUNDING_CHARS = 5000
TOP_K_CHUNKS = 6


class StudyContentError(Exception):
    """A request the caller must be told about, with its own status code."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


# ------------------------------------------------------------------ identity


def active_structure(db, username, course_id):
    """The version this learner is studying from, or None — never the draft."""
    from . import knowledge_structure as structure_service

    key = normalize_course_id(course_id)
    return structure_service.active_structure(db, username, key)


def resolve_point(db, username, course_id, point_id):
    """The learner's OWN point, in the ACTIVE version — or a refusal.

    Both halves matter. Without the username a point id from another learner would be
    readable; without the active-version filter a point belonging to a draft or to a
    superseded version would be presented as part of the course the learner is studying, and
    it is not.
    """
    from models import KnowledgePoint

    key = normalize_course_id(course_id)
    forms = course_identity_forms(key)
    row = (db.query(KnowledgePoint)
           .filter(KnowledgePoint.id == int(point_id),
                   KnowledgePoint.username == username,
                   KnowledgePoint.course_id.in_(sorted(forms)))
           .first())
    if row is None:
        raise StudyContentError("知识点不存在", 404)

    active = active_structure(db, username, key)
    expected = active.id if active is not None else None
    if row.structure_id != expected:
        # The point exists but is not the one this learner studies from. Saying "not found"
        # rather than explaining versions keeps a superseded point from looking like a
        # page-level error the learner should somehow fix.
        raise StudyContentError("知识点不存在", 404)
    return row, active


def chapter_of(db, username, point) -> str:
    """The chapter title a point sits under, or "" when it has no parent."""
    from models import KnowledgePoint

    if not point.parent_id:
        return ""
    parent = (db.query(KnowledgePoint)
              .filter(KnowledgePoint.id == point.parent_id,
                      KnowledgePoint.username == username)
              .first())
    return (parent.title if parent else "") or ""


# ------------------------------------------------------------------ grounding


def _point_linked_material_ids(db, username, course_id, point_id) -> list[int]:
    """Files the learner explicitly attached to this point.

    Empty for almost every learner today — generation does not write these links — which is
    exactly why they are read first: when they DO exist they are the most specific statement
    available about which file covers this point.
    """
    from models import MaterialKnowledgeLink

    forms = sorted(course_identity_forms(normalize_course_id(course_id)))
    rows = (db.query(MaterialKnowledgeLink.material_id)
            .filter(MaterialKnowledgeLink.username == username,
                    MaterialKnowledgeLink.course_id.in_(forms),
                    MaterialKnowledgeLink.knowledge_point_id == int(point_id))
            .all())
    return sorted({int(row[0]) for row in rows if row[0]})


def _structure_source_file_ids(structure) -> list[int]:
    if structure is None or not structure.source_file_ids:
        return []
    try:
        values = json.loads(structure.source_file_ids)
    except (TypeError, ValueError):
        return []
    out: list[int] = []
    for value in values if isinstance(values, list) else []:
        try:
            number = int(value)
        except (TypeError, ValueError):
            continue
        if number and number not in out:
            out.append(number)
    return out


def grounding_plan(db, username, course_id, point_id) -> tuple[str, list[int]]:
    """(mode, material ids) for this point — the ONLY place the grounding rule is decided.

    `selected_materials` grounds in the structure's own files, because those are what the
    tree was organized from. `ai_generated` grounds in the whole course library, because the
    learner's files are not the tree's source and the only honest relation left is "these are
    the materials of this course". Either way the point's own explicit links are added.
    """
    linked = _point_linked_material_ids(db, username, course_id, point_id)
    structure = active_structure(db, username, course_id)

    if structure is not None and structure.source_mode == GROUNDING_SELECTED_MATERIALS:
        ids = _structure_source_file_ids(structure)
        for value in linked:
            if value not in ids:
                ids.append(value)
        return (GROUNDING_SELECTED_MATERIALS, ids) if ids else (GROUNDING_NONE, [])

    if linked:
        return GROUNDING_SELECTED_MATERIALS, linked
    return GROUNDING_AI_GENERATED, []


def _course_material_ids(db, username, course_id) -> list[int]:
    from models import StudyMaterial

    forms = sorted(course_identity_forms(normalize_course_id(course_id)))
    rows = (db.query(StudyMaterial.id)
            .filter(StudyMaterial.username == username,
                    StudyMaterial.is_deleted.is_(False),
                    StudyMaterial.course_id.in_(forms))
            .all())
    return [int(row[0]) for row in rows if row[0]]


def _retrieve(db, username, course_id, question, mode, material_ids) -> list[dict]:
    """The passages this explanation may use, from the pool the grounding rule named.

    Both branches narrow by material id BEFORE ranking, so a chunk from a course the learner
    did not ask about cannot be pulled in by a keyword collision.
    """
    from rag import retrieve_chunks_for_materials

    if mode == GROUNDING_SELECTED_MATERIALS:
        if not material_ids:
            return []
        return retrieve_chunks_for_materials(username, course_id, question,
                                             material_ids, top_k=TOP_K_CHUNKS)

    ids = _course_material_ids(db, username, course_id)
    if not ids:
        return []
    return retrieve_chunks_for_materials(username, course_id, question, ids,
                                         top_k=TOP_K_CHUNKS)


def _chunk_text(chunk: dict) -> str:
    return str(chunk.get("chunk_summary") or chunk.get("chunk_text") or "").strip()


def _render_grounding(chunks: list[dict]) -> tuple[str, list[dict]]:
    """The prompt's material block AND the citations the learner will see.

    The two are built together on purpose: a citation is a claim that this file grounded this
    answer, and deriving the list from the same chunks that were actually sent is what keeps
    that claim true.
    """
    lines: list[str] = []
    citations: list[dict] = []
    seen: set[str] = set()
    total = 0
    for chunk in chunks:
        text = _chunk_text(chunk)
        if not text:
            continue
        name = str(chunk.get("source_filename") or "").strip() or "学习资料"
        line = f"【{name}】\n{text[:1200]}"
        if total + len(line) > MAX_GROUNDING_CHARS:
            break
        lines.append(line)
        total += len(line)
        if name not in seen:
            seen.add(name)
            citations.append({"filename": name, "snippet": text[:200]})
    return "\n\n".join(lines), citations


def grounding_text(db, username: str, course_id: str, point_id: int,
                   query: str = "", limit: int = 1600) -> str:
    """The learner's own material about ONE point, as plain text — no citations.

    Exposed so the practice generator can let a question use the terminology and examples the
    learner actually has, through the SAME grounding rule the explanation uses. Deciding that
    rule twice would let 学习 and 练习 disagree about which files are this point's, and a
    question built on a file the explanation does not cite is worse than no grounding at all.

    Best-effort by construction: retrieval is a keyword read of the learner's own chunks, and
    an empty string means "no material to lean on", never an error. Nothing is stored.
    """
    mode, material_ids = grounding_plan(db, username, course_id, point_id)
    chunks = _retrieve(db, username, course_id, query or str(point_id), mode, material_ids)
    text, _ = _render_grounding(chunks)
    return text[:limit]


# ------------------------------------------------------------------ prompt

_SYSTEM_PROMPT = (
    "你是一位大学课程助教，正在帮学生弄懂一个具体知识点。"
    "用学生能直接看懂的中文讲解，结构清楚但不套模板：先讲清是什么，再讲核心要点，"
    "需要时给一个具体例子，最后点出容易混淆或出错的地方。"
    "只讲这个知识点本身，不要扩展成整章综述。"
    "不要出现任何关于你自己的说明，不要提资料检索、模型、置信度或类似内容，"
    "也不要写“以下是详细讲解”“作为一个AI”这类开场白。"
)

_USER_PROMPT = """课程：{course}
{chapter_line}知识点：{title}
{description_line}
{material_block}请讲解这个知识点。直接开始讲内容。"""


def _build_messages(course_id, chapter, point, grounding_text) -> list[dict]:
    material_block = ""
    if grounding_text:
        material_block = f"\n以下是与本知识点相关的课程资料片段，讲解要贴合它们：\n\n{grounding_text}\n\n"
    user_prompt = _USER_PROMPT.format(
        course=course_id,
        chapter_line=f"章节：{chapter}\n" if chapter else "",
        title=point.title,
        description_line=(f"说明：{point.description}\n" if (point.description or "").strip()
                          else ""),
        material_block=material_block,
    )
    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]


# ------------------------------------------------------------------ cache


def _citations_out(raw) -> list[dict]:
    if not raw:
        return []
    try:
        values = json.loads(raw)
    except (TypeError, ValueError):
        return []
    out: list[dict] = []
    for value in values if isinstance(values, list) else []:
        if not isinstance(value, dict):
            continue
        name = str(value.get("filename") or "").strip()
        if not name:
            continue
        out.append({"filename": name, "snippet": str(value.get("snippet") or "")})
    return out


def _serialize(row) -> dict:
    return {
        "knowledge_point_id": row.knowledge_point_id,
        "course_id": row.course_id,
        "content": row.content,
        "citations": _citations_out(row.citations_json),
        "grounding_mode": row.grounding_mode or GROUNDING_NONE,
        "generated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def read_cached(db, username, point_id):
    """The explanation already stored for this point — or None. Never generates."""
    from models import KnowledgePointStudyContent

    row = (db.query(KnowledgePointStudyContent)
           .filter(KnowledgePointStudyContent.username == username,
                   KnowledgePointStudyContent.knowledge_point_id == int(point_id))
           .first())
    return _serialize(row) if row is not None else None


def _store(db, username, course_id, point, structure, content, citations, mode):
    from models import KnowledgePointStudyContent

    row = (db.query(KnowledgePointStudyContent)
           .filter(KnowledgePointStudyContent.username == username,
                   KnowledgePointStudyContent.knowledge_point_id == int(point.id))
           .first())
    payload = json.dumps(citations, ensure_ascii=False)
    if row is None:
        row = KnowledgePointStudyContent(
            username=username, course_id=normalize_course_id(course_id),
            knowledge_point_id=int(point.id), content=content)
        db.add(row)
    row.course_id = normalize_course_id(course_id)
    row.structure_id = getattr(structure, "id", None)
    row.content = content
    row.citations_json = payload
    row.grounding_mode = mode
    db.commit()
    db.refresh(row)
    return _serialize(row)


# ------------------------------------------------------------------ the operation


def study_content(db, user, course_id, point_id, *, regenerate: bool = False) -> dict:
    """The explanation for ONE point: the stored one, or a freshly grounded one.

    Reading a stored explanation costs nothing and calls nothing — which is the whole point
    of storing it. A regenerate replaces it; the learner asked for a new one, so returning
    the old row instead would be a refusal dressed as success.
    """
    point, structure = resolve_point(db, user.username, course_id, point_id)

    if not regenerate:
        cached = read_cached(db, user.username, point.id)
        if cached is not None:
            return {**cached, "cached": True}

    chapter = chapter_of(db, user.username, point)
    mode, material_ids = grounding_plan(db, user.username, course_id, point.id)
    chunks = _retrieve(db, user.username, course_id, point.title, mode, material_ids)
    grounding_text, citations = _render_grounding(chunks)
    if not grounding_text:
        # Nothing to cite means nothing was cited. Claiming a material grounded the answer
        # because a link row exists would be a fabricated citation.
        mode = GROUNDING_NONE

    from main import _course_ai_result

    result = _course_ai_result(
        db, user, CAPABILITY, _build_messages(course_id, chapter, point, grounding_text),
        course_id=normalize_course_id(course_id), chapter_id=chapter or None,
        knowledge_point_id=str(point.id), material_ids=material_ids or None,
        max_tokens=OUTPUT_TOKEN_BUDGET)

    content = (result.content or "").strip()
    if not content:
        raise StudyContentError("这次没有生成内容，请重试。", 502)

    stored = _store(db, user.username, course_id, point, structure,
                    content, citations, mode)
    return {**stored, "cached": False}
