"""The learner's OWN knowledge structure for a course — versioned, never replaced in place.

WHAT THIS OWNS
--------------
Everything a learner sees under 课程 → 知识结构, and everything that reads the structure
they study from: the active tree, the draft a generation produced, confirming or
discarding that draft, and the light edits a draft accepts before it is confirmed.

WHY IT IS USER-SCOPED, AND WHY THAT IS ALREADY TRUE
---------------------------------------------------
The structure is USER + COURSE data, not a shared catalogue. Two learners taking 数据结构
may each build a tree from their own materials, and neither generation may touch the
other's points, progress, wrong answers or review schedule. That boundary predates this
module — ``knowledge_points`` has always carried ``username`` — so nothing here introduces
a new scope. What is new is the VERSION.

WHY A VERSION
-------------
Before this module, generating a structure REPLACED the previous one in place: the old
points were deleted, and their ``user_knowledge_progress`` rows, wrong-answer links and
review schedule were deleted with them. A learner who had mastered four chapters and then
regenerated from a second textbook lost that record silently.

So a generate writes a ``draft``. The version actually being studied stays ``active`` and
untouched until the learner confirms the draft; the replaced version is then marked
``superseded`` — kept, not deleted — so the progress rows that reference its points survive
the switch. Nothing is ever destroyed except a draft the learner explicitly discards, and a
draft never had progress to lose.

WHERE THE CONTENT COMES FROM, AND WHY IT IS RECORDED
----------------------------------------------------
``source_mode`` says how the structure's content was obtained:

    selected_materials  the learner picked files from their own course library, and the
                        model was asked to organize THOSE files
    ai_generated        the model was asked for a structure for the course; no file was
                        its source

Each point additionally carries ``origin``: ``source_extracted`` when the model named the
selected file it took the point from, ``ai_inferred`` when it supplied the point itself.
The distinction is internal provenance — a learner is never shown the enum — but it is what
stops an invented tree from later being presented as extracted from the learner's own
files. That is the whole reason it is stored rather than inferred at read time.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime

from sqlalchemy.orm import Session as DbSession

from .context import course_identity_forms, normalize_course_id

logger = logging.getLogger("learning.spaces.course_learning")

STRUCTURE_DRAFT = "draft"
STRUCTURE_ACTIVE = "active"
STRUCTURE_SUPERSEDED = "superseded"

SOURCE_MODE_SELECTED_MATERIALS = "selected_materials"
SOURCE_MODE_AI_GENERATED = "ai_generated"

ORIGIN_SOURCE_EXTRACTED = "source_extracted"
ORIGIN_AI_INFERRED = "ai_inferred"

GOALS = ("期末考试", "考研", "系统学习")

# Generation granularity (§11). A course is neither "8 points" nor "800 fragments", so the
# prompt asks for a range. The range is bounded by what the response BUDGET can actually
# deliver: a JSON answer is roughly 25 output tokens per point, so 8 chapters × 8 points sits
# comfortably inside ``OUTPUT_TOKEN_BUDGET`` while 12 × 16 did not — that ask produced an
# answer long enough to be cut off mid-object, which parses as nothing at all and surfaced to
# the learner as a bare failure.
PROMPT_MIN_CHAPTERS, PROMPT_MAX_CHAPTERS = 4, 8
PROMPT_MIN_POINTS_PER_CHAPTER, PROMPT_MAX_POINTS_PER_CHAPTER = 3, 8

# The HARD caps the parser enforces, kept above the range asked for so a model that
# overshoots by a little is trimmed rather than thrown away — and set so that the total can
# actually bind: MAX_CHAPTERS × MAX_POINTS_PER_CHAPTER exceeds MAX_POINTS_TOTAL, which is
# what makes the total a real ceiling instead of a number nothing can reach.
MAX_CHAPTERS = 40
MAX_POINTS_PER_CHAPTER = 40
MAX_POINTS_TOTAL = 600

# The output budget this module reserves and sends. Above the default chat ceiling because a
# whole course structure is one long JSON object, and a structure cut off in the middle is not
# a shorter structure — it is an unparseable answer.
OUTPUT_TOKEN_BUDGET = 3000

MAX_MATERIAL_CHARS = 18000
MAX_CHUNKS_PER_MATERIAL = 12
MAX_SOURCE_FILES = 40


class KnowledgeStructureError(Exception):
    """A generation or edit the caller must be told about, with its own status code."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


# ------------------------------------------------------------------ identity + reads

def _scope_forms(course_id) -> tuple[str, frozenset[str]]:
    key = normalize_course_id(course_id)
    return key, course_identity_forms(key)


def _user_id(db, username) -> int | None:
    from models import User
    user = db.query(User).filter(User.username == username).first()
    return getattr(user, "id", None)


def _structures(db, username, forms, status=None):
    from models import UserKnowledgeStructure
    query = db.query(UserKnowledgeStructure).filter(
        UserKnowledgeStructure.username == username,
        UserKnowledgeStructure.course_id.in_(sorted(forms)),
    )
    if status is not None:
        query = query.filter(UserKnowledgeStructure.status == status)
    return query.order_by(UserKnowledgeStructure.version.desc(),
                          UserKnowledgeStructure.id.desc()).all()


def active_structure(db, username, course_id):
    key, forms = _scope_forms(course_id)
    rows = _structures(db, username, forms, STRUCTURE_ACTIVE)
    return rows[0] if rows else None


def draft_structure(db, username, course_id):
    """The most recent draft. At most one is kept per course — see ``create_draft``."""
    key, forms = _scope_forms(course_id)
    rows = _structures(db, username, forms, STRUCTURE_DRAFT)
    return rows[0] if rows else None


def _points(db, username, forms, structure_id):
    from models import KnowledgePoint
    query = db.query(KnowledgePoint).filter(
        KnowledgePoint.username == username,
        KnowledgePoint.course_id.in_(sorted(forms)))
    if structure_id is None:
        query = query.filter(KnowledgePoint.structure_id.is_(None))
    else:
        query = query.filter(KnowledgePoint.structure_id == structure_id)
    return query.order_by(KnowledgePoint.order_index.asc(),
                          KnowledgePoint.id.asc()).all()


def build_tree(points) -> list[dict]:
    """Two levels, chapters then points — the shape the page renders.

    Depth is deliberately fixed at two: the generated structures are two-level, and a
    recursive renderer would be scaffolding for a third level that no writer produces.
    A point whose chapter is missing (a deleted chapter, a foreign structure id) is
    surfaced under its own chapter rather than dropped, because a point that silently
    disappears from the page is indistinguishable from a point that was never generated.
    """
    by_parent: dict[int | None, list] = {}
    for point in points:
        by_parent.setdefault(point.parent_id, []).append(point)

    def point_view(point) -> dict:
        return {
            "id": point.id,
            "title": point.title,
            "description": point.description or "",
            "origin": point.origin or ORIGIN_AI_INFERRED,
        }

    chapters = []
    for chapter in by_parent.get(None, []):
        chapters.append({
            "id": chapter.id,
            "title": chapter.title,
            "description": chapter.description or "",
            "points": [point_view(child) for child in by_parent.get(chapter.id, [])],
        })
    orphans = [point_view(point) for point in points if point.parent_id is not None
               and point.parent_id not in {c.id for c in by_parent.get(None, [])}]
    if orphans:
        chapters.append({"id": None, "title": "未归入章节", "description": "",
                         "points": orphans})
    return chapters


def _structure_view(structure) -> dict | None:
    if structure is None:
        return None
    try:
        file_ids = json.loads(structure.source_file_ids) if structure.source_file_ids else []
    except (TypeError, ValueError):
        file_ids = []
    return {
        "id": structure.id,
        "version": structure.version,
        "status": structure.status,
        "source_mode": structure.source_mode,
        "source_file_ids": [int(value) for value in file_ids if str(value).isdigit()],
        "title": structure.title or "",
        "goal": structure.goal or "",
        "point_count": structure.point_count or 0,
        "chapter_count": structure.chapter_count or 0,
        "created_at": structure.created_at,
        "confirmed_at": structure.confirmed_at,
    }


def describe(db, username, course_id) -> dict:
    """Everything the knowledge-structure page needs, in one read.

    ``chapters`` is the tree to DISPLAY: the draft when one exists, otherwise the active
    structure. A draft is the learner's current question ("do I want this?"), so showing
    the active tree while a draft waits would hide the very thing the page is about.
    """
    key, forms = _scope_forms(course_id)
    active = active_structure(db, username, key)
    draft = draft_structure(db, username, key)

    shown = draft or active
    points = _points(db, username, forms, shown.id) if shown is not None else []
    chapters = build_tree(points)

    return {
        "course_id": key,
        "display": STRUCTURE_DRAFT if draft else (STRUCTURE_ACTIVE if active else "none"),
        "active": _structure_view(active),
        "draft": _structure_view(draft),
        "chapters": chapters,
        "carry_over": carry_over_preview(db, username, key) if draft else None,
    }


# ------------------------------------------------------------------ progress safety

_NUMBERING = re.compile(r"^\s*(?:第\s*)?\d+(?:\s*[.、章节讲])?(?:\s*\d+)?\s*[.、]?\s*")


def match_key(title: str) -> str:
    """How two knowledge-point titles are decided to be the SAME topic.

    Numbering and punctuation are stripped because the same topic is written "1.1 顺序表"
    in one structure and "顺序表" in the next; anything past that is preserved, because
    "顺序表" and "单链表" must not collapse into one another. Case is folded only for
    Latin text, which is the one place a case difference carries no meaning.
    """
    value = (title or "").strip().lower()
    value = _NUMBERING.sub("", value)
    value = re.sub(r"[\s　·:：,，。.、()（）\[\]【】\-—_/]+", "", value)
    return value


def carry_over_preview(db, username, course_id) -> dict:
    """What confirming the current draft would do to the learner's progress.

    Reported, never applied. The page shows these numbers before the learner confirms,
    because "your progress will be kept" is a claim that has to be checkable, and because
    the alternative — switching and hoping — is how progress gets lost without anyone
    noticing.
    """
    key, forms = _scope_forms(course_id)
    active = active_structure(db, username, key)
    draft = draft_structure(db, username, key)
    if draft is None:
        return {"available": False}

    new_points = _points(db, username, forms, draft.id)
    old_points = _points(db, username, forms, active.id) if active else []

    old_keys = {match_key(point.title) for point in old_points if match_key(point.title)}
    new_keys = {match_key(point.title) for point in new_points if match_key(point.title)}
    matched = len(old_keys & new_keys)

    progressed_ids = _progressed_point_ids(db, username, old_points)
    # The number the learner actually cares about: of the topics they HAVE recorded learning
    # on, how many are in the new structure. Counting every matched title instead would fold
    # in chapters and untouched points and overstate what is at stake.
    progressed_matched = len([
        point for point in old_points
        if point.id in progressed_ids and match_key(point.title) in new_keys])
    progressed_unmatched = len(progressed_ids) - progressed_matched

    return {
        "available": True,
        "has_progress": bool(progressed_ids),
        "progressed_points": len(progressed_ids),
        "matched_progressed_points": progressed_matched,
        "unmatched_progressed_points": progressed_unmatched,
        "active_point_count": len(old_points),
        "draft_point_count": len(new_points),
        "matched_point_count": matched,
        "unmatched_active_points": max(0, len(old_keys) - matched),
    }


def _progressed_point_ids(db, username, points) -> set[int]:
    """The points that carry a real learning record worth protecting.

    ``mastery_score > 0`` OR a status other than ``not_started`` — either alone means the
    learner did something here, and a topic with a record is a topic that must not lose it.
    """
    from models import UserKnowledgeProgress
    ids = [point.id for point in points]
    if not ids:
        return set()
    rows = (db.query(UserKnowledgeProgress.knowledge_point_id)
            .filter(UserKnowledgeProgress.username == username,
                    UserKnowledgeProgress.knowledge_point_id.in_(ids),
                    (UserKnowledgeProgress.mastery_score > 0)
                    | (UserKnowledgeProgress.status != "not_started"))
            .all())
    return {row[0] for row in rows}


_PROGRESS_CARRIED_FIELDS = (
    "mastery_score", "status", "user_confirmed_status", "system_suggested_status",
    "ai_recommended_status", "practice_count", "task_count", "last_studied_at",
    "learned_at", "review_due_at", "review_interval_days",
)


def _carry_progress(db, username, user_id, old_points, new_points) -> dict:
    """Move surviving progress from the superseded points onto the new ones.

    A topic that exists in both structures keeps everything the learner earned on it. A
    topic only in the OLD structure keeps its row too — that row references a point that
    still exists (the version is superseded, not deleted), so it is not orphaned and not
    zeroed. Nothing is deleted here at all; this function only copies forward.
    """
    from models import UserKnowledgeProgress

    old_keys = {}
    for point in old_points:
        key = match_key(point.title)
        if key and key not in old_keys:
            old_keys[key] = point
    if not old_keys:
        return {"carried": 0, "kept_on_previous_version": 0, "points": []}

    old_ids = [point.id for point in old_keys.values()]
    rows = (db.query(UserKnowledgeProgress)
            .filter(UserKnowledgeProgress.username == username,
                    UserKnowledgeProgress.knowledge_point_id.in_(old_ids))
            .all())
    by_point = {row.knowledge_point_id: row for row in rows}

    now = datetime.utcnow()
    new_ids = [point.id for point in new_points]
    existing_new = {}
    if new_ids:
        existing_new = {
            row.knowledge_point_id: row
            for row in db.query(UserKnowledgeProgress)
            .filter(UserKnowledgeProgress.username == username,
                    UserKnowledgeProgress.knowledge_point_id.in_(new_ids))
            .all()
        }

    carried = 0
    touched = []
    for point in new_points:
        source = old_keys.get(match_key(point.title))
        if source is None:
            continue
        progress = by_point.get(source.id)
        if progress is None:
            continue
        target = existing_new.get(point.id)
        if target is None:
            target = UserKnowledgeProgress(
                user_id=user_id, username=username, course_id=point.course_id,
                knowledge_point_id=point.id, knowledge_point_code=point.node_key,
                knowledge_point_title=point.title, created_at=now)
            db.add(target)
        for field in _PROGRESS_CARRIED_FIELDS:
            setattr(target, field, getattr(progress, field, None))
        target.knowledge_point_title = point.title
        target.updated_at = now
        carried += 1
        touched.append({"from_point_id": source.id, "to_point_id": point.id,
                        "status": progress.status})
    db.flush()

    matched_old_ids = {old_keys[match_key(point.title)].id
                       for point in new_points if match_key(point.title) in old_keys}
    kept = len([point for point in old_points if point.id not in matched_old_ids])
    return {"carried": carried, "kept_on_previous_version": kept, "points": touched}


# ------------------------------------------------------------------ generation

def _chapter_payload(raw_chapters: list) -> list[dict]:
    """The model's answer, held to the shape and size this module stores.

    Anything the model gets wrong about the SHAPE (a chapter with no title, a point with
    no title) is dropped rather than repaired: a point named "" is not a knowledge point,
    and inventing a name for it would put a topic in the learner's structure that neither
    they nor the model asked for.
    """
    chapters: list[dict] = []
    for raw_chapter in raw_chapters or []:
        if not isinstance(raw_chapter, dict):
            continue
        title = str(raw_chapter.get("title") or "").strip()
        if not title:
            continue
        points = []
        for raw_point in raw_chapter.get("points") or raw_chapter.get("knowledge_points") or []:
            if isinstance(raw_point, str):
                raw_point = {"title": raw_point}
            if not isinstance(raw_point, dict):
                continue
            point_title = str(raw_point.get("title") or "").strip()
            if not point_title:
                continue
            hint = str(raw_point.get("source_hint") or raw_point.get("source") or "").strip()
            points.append({
                "title": point_title[:255],
                "description": str(raw_point.get("description") or "").strip()[:255],
                "source_hint": hint[:255],
            })
            if len(points) >= MAX_POINTS_PER_CHAPTER:
                break
        if not points:
            continue
        chapters.append({
            "title": title[:255],
            "description": str(raw_chapter.get("description") or "").strip()[:255],
            "points": points,
        })
        if len(chapters) >= MAX_CHAPTERS:
            break
    return chapters


def parse_structure_json(raw: str) -> list[dict]:
    """The model's JSON, however it arrived, as a chapter list.

    Providers wrap JSON in fences, prepend a sentence, or return a bare list where an
    object was asked for; all three are the same answer and all three are accepted. A
    response with nothing usable is an error, not an empty structure — silently storing
    zero chapters would look to the learner like a generation that succeeded.
    """
    text = (raw or "").strip()
    if not text:
        raise KnowledgeStructureError("AI 没有返回内容，请重试。", 502)
    fence = re.search(r"```(?:json)?\s*(.+?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    payload = None
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        start = min((i for i in (text.find("{"), text.find("[")) if i >= 0), default=-1)
        end = max(text.rfind("}"), text.rfind("]"))
        if start >= 0 and end > start:
            try:
                payload = json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                payload = None
    if payload is None:
        raise KnowledgeStructureError(
            "AI 这次没有返回完整的结构，请再试一次。", 502)

    if isinstance(payload, list):
        raw_chapters = payload
    elif isinstance(payload, dict):
        raw_chapters = (payload.get("chapters") or payload.get("modules")
                        or payload.get("knowledge_structure") or [])
    else:
        raw_chapters = []

    chapters = _chapter_payload(raw_chapters)
    if not chapters:
        raise KnowledgeStructureError("AI 没有生成可用的章节，请重试或换一种来源。", 502)
    return chapters


def _material_lines(db, username, course_id, material_ids: list[int]):
    """The selected files' own text, as the only content the model may organize."""
    from models import MaterialChunk, StudyMaterial

    forms = sorted(course_identity_forms(course_id))
    materials = (db.query(StudyMaterial)
                 .filter(StudyMaterial.id.in_(material_ids),
                         StudyMaterial.username == username,
                         StudyMaterial.is_deleted.is_(False))
                 .all())
    if len(materials) != len(set(material_ids)):
        raise KnowledgeStructureError("所选资料不存在，或不属于当前账号。")

    chunks = (db.query(MaterialChunk)
              .filter(MaterialChunk.material_id.in_(material_ids),
                      MaterialChunk.username == username,
                      MaterialChunk.is_deleted.is_(False))
              .order_by(MaterialChunk.material_id, MaterialChunk.chunk_index)
              .all())

    by_id = {material.id: material for material in materials}
    names = [by_id[mid].original_filename for mid in material_ids if mid in by_id]
    lines: list[str] = []
    total = 0
    per_material: dict[int, int] = {}
    for chunk in chunks:
        if per_material.get(chunk.material_id, 0) >= MAX_CHUNKS_PER_MATERIAL:
            continue
        value = (chunk.chunk_summary or chunk.chunk_text or "").strip()
        if not value:
            continue
        material = by_id.get(chunk.material_id)
        source_name = material.original_filename if material else chunk.source_filename
        line = f"【{source_name} - 片段 {chunk.chunk_index + 1}】\n{value[:1200]}"
        if total + len(line) > MAX_MATERIAL_CHARS:
            break
        lines.append(line)
        total += len(line)
        per_material[chunk.material_id] = per_material.get(chunk.material_id, 0) + 1
    return names, lines, materials


def _canonical_outline(course_id) -> str:
    """The shipped course structure, when this build has one, as a naming reference.

    Used for AI generation only, and only as the ORGANIZING SYSTEM — never as content.
    For the 408 subjects this is the syllabus the product already publishes, so a learner
    asking for 数据结构 gets chapters that match the canonical course rather than a
    plausible-sounding invention. For a course with no shipped structure the model is told
    nothing and must not pretend to know a particular textbook.

    The directory is read directly rather than through ``main``: importing the application
    module from a domain module would run the app's startup (including its schema preflight)
    as a side effect of building a prompt. ``test_the_reference_directory_is_the_one_the_app_serves``
    pins this path against ``main``'s constant so the two cannot drift apart unnoticed.
    """
    from subjects import resolve_course_id_from_display

    candidates = [course_id, resolve_course_id_from_display(course_id) or ""]
    for candidate in candidates:
        if not candidate:
            continue
        path = _knowledge_map_seed_path(candidate)
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            # The file IS there and could not be read — that is a broken asset, not "this
            # course has no reference", and it must be visible rather than silently
            # downgrading the prompt to an unpinned invention.
            logger.warning("knowledge structure reference %s unreadable: %s",
                           path.name, type(exc).__name__)
            return ""
        titles = []
        for chapter in payload.get("chapters") or []:
            chapter_title = str(chapter.get("title") or "").strip()
            if chapter_title:
                titles.append(chapter_title)
        return "\n".join(f"- {title}" for title in titles[:20])
    return ""


def _knowledge_map_seed_path(course_id: str):
    """``seed_data/knowledge_maps/<course_id>.json`` — the same sanitizer ``main`` applies."""
    from pathlib import Path

    base = Path(__file__).resolve().parents[3]
    safe = re.sub(r"[^a-zA-Z0-9_-]", "", course_id or "")
    return base / "seed_data" / "knowledge_maps" / f"{safe}.json"


_MATERIAL_SYSTEM_PROMPT = (
    "你是大学课程知识结构整理助手。你的任务是把给定的课程资料整理成「章节 → 知识点」"
    "两层结构。只输出严格 JSON，不要 Markdown，不要解释。"
)

_MATERIAL_USER_PROMPT = """课程：{course}
所选资料：
{names}

资料片段：
{chunks}

请输出 JSON：
{{
  "chapters": [
    {{
      "title": "章节标题",
      "points": [
        {{"title": "知识点标题", "description": "一句话说明", "source_hint": "来自哪个资料文件名"}}
      ]
    }}
  ]
}}

要求：
1. 生成 {min_chapters}-{max_chapters} 个章节，每章 {min_points}-{max_points} 个知识点。
2. 知识点标题必须来自资料中真实出现的章节标题、小节标题或正文关键概念。
3. 只整理资料里有的内容。只在资料确实不足以覆盖该课程主要脉络时，才补充少量必要知识点，
   并把这些知识点的 source_hint 留空字符串。
4. 不要把例题编号、页眉页脚、作业标题、页码、无意义的文字碎片当作知识点。
5. 标题要短，适合列表展示。
6. 严格输出 JSON，不要包含 ```json。"""

_AI_SYSTEM_PROMPT = (
    "你是大学课程知识结构整理助手。你要为学生生成一份「章节 → 知识点」两层知识结构。"
    "只输出严格 JSON，不要 Markdown，不要解释。"
)

_AI_USER_PROMPT = """课程：{course}
学习目标：{goal}
补充要求：{requirement}

{outline_block}
请输出 JSON：
{{
  "chapters": [
    {{
      "title": "章节标题",
      "points": [{{"title": "知识点标题", "description": "一句话说明"}}]
    }}
  ]
}}

要求：
1. 生成 {min_chapters}-{max_chapters} 个章节，每章 {min_points}-{max_points} 个知识点。
2. 知识结构必须符合这门课程公开、通用的知识体系，从基础到进阶排序。
3. 不要编造某位老师特定的教材章节；不知道就用通用体系。
4. 不要输出 source_hint 字段。
5. 严格输出 JSON，不要包含 ```json。"""


def _call_ai(db, user, course_id, material_ids, system_prompt, user_prompt) -> str:
    from .ai import execute_course_ai
    from .context import build_course_context

    result = execute_course_ai(
        db, user, "knowledge.structure",
        [{"role": "system", "content": system_prompt},
         {"role": "user", "content": user_prompt}],
        learning_context=build_course_context(
            user, course_id=course_id,
            material_ids=material_ids or None),
        temperature=0.2,
        max_tokens=OUTPUT_TOKEN_BUDGET)
    return result.content


def generate_from_materials(db, user, course_id, material_ids: list[int]) -> list[dict]:
    """Organize the learner's OWN selected files into a chapter list.

    Every point's origin is decided HERE, not by the model's self-report: a point is
    ``source_extracted`` when the model named the file it came from and that name is one
    of the files the learner actually selected, and ``ai_inferred`` otherwise. A model
    that invents a source name does not get to label its invention as extracted.
    """
    key = normalize_course_id(course_id)
    names, lines, materials = _material_lines(db, user.username, key, material_ids)
    if not lines:
        raise KnowledgeStructureError(
            "所选资料还没有可用的知识片段，请先在资料库完成 AI 索引。")
    if not names:
        raise KnowledgeStructureError("所选资料不存在，或不属于当前账号。")

    prompt = _MATERIAL_USER_PROMPT.format(
        course=key, names="\n".join(f"- {name}" for name in names),
        chunks="\n".join(lines),
        min_chapters=PROMPT_MIN_CHAPTERS, max_chapters=PROMPT_MAX_CHAPTERS,
        min_points=PROMPT_MIN_POINTS_PER_CHAPTER,
        max_points=PROMPT_MAX_POINTS_PER_CHAPTER)
    raw = _call_ai(db, user, key, material_ids, _MATERIAL_SYSTEM_PROMPT, prompt)
    chapters = parse_structure_json(raw)

    known = {name.strip().lower() for name in names}
    for chapter in chapters:
        for point in chapter["points"]:
            hint = (point.get("source_hint") or "").strip().lower()
            point["origin"] = (ORIGIN_SOURCE_EXTRACTED
                               if hint and hint in known else ORIGIN_AI_INFERRED)
    return chapters


def generate_from_ai(db, user, course_id, goal: str = "", requirement: str = "") -> list[dict]:
    """A structure for the course with no file as its source.

    Recorded as ``ai_generated`` and every point as ``ai_inferred`` — which is what it is.
    Presenting this as parsed from course material would be the fabrication the SSOT
    forbids, and the learner is told plainly that it is an AI draft they are about to
    accept.
    """
    key = normalize_course_id(course_id)
    outline = _canonical_outline(key)
    outline_block = (
        f"这门课程在本产品里已有公认的课程体系，请按它组织章节：\n{outline}\n"
        if outline else
        "这门课程本产品没有内置课程体系，请按该课程公开、通用的知识体系组织。\n"
    )
    prompt = _AI_USER_PROMPT.format(
        course=key, goal=(goal or "系统学习"), requirement=(requirement or "无"),
        outline_block=outline_block,
        min_chapters=PROMPT_MIN_CHAPTERS, max_chapters=PROMPT_MAX_CHAPTERS,
        min_points=PROMPT_MIN_POINTS_PER_CHAPTER,
        max_points=PROMPT_MAX_POINTS_PER_CHAPTER)
    raw = _call_ai(db, user, key, [], _AI_SYSTEM_PROMPT, prompt)
    chapters = parse_structure_json(raw)
    for chapter in chapters:
        for point in chapter["points"]:
            point["origin"] = ORIGIN_AI_INFERRED
            point["source_hint"] = ""
    return chapters


# ------------------------------------------------------------------ draft lifecycle

def _next_version(db, username, forms) -> int:
    rows = _structures(db, username, forms)
    return max((row.version or 1) for row in rows) + 1 if rows else 1


def create_draft(db, user, course_id, *, source_mode: str, chapters: list[dict],
                 source_file_ids: list[int] | None = None,
                 title: str = "", goal: str = ""):
    """Store a generation as a DRAFT. The active structure is not touched.

    The previous draft for this course is discarded first. A learner who regenerates three
    times has one draft — the one they are looking at — not three, and discarding a draft
    destroys only generated content that was never studied from.
    """
    from models import KnowledgePoint, UserKnowledgeStructure

    key, forms = _scope_forms(course_id)
    if source_mode not in (SOURCE_MODE_SELECTED_MATERIALS, SOURCE_MODE_AI_GENERATED):
        raise KnowledgeStructureError("来源类型无效。")

    chapters = _chapter_payload(chapters)
    if not chapters:
        raise KnowledgeStructureError("没有可用的章节，无法生成知识结构。")

    total = sum(len(chapter["points"]) for chapter in chapters)
    if total > MAX_POINTS_TOTAL:
        raise KnowledgeStructureError(
            f"生成的知识点过多（{total} 个），请减少资料范围后重试。")
    # There is no floor beyond "at least one point in at least one chapter", which
    # ``_chapter_payload`` already guarantees. A small course is a small structure, not an
    # error: refusing it would tell a learner their real course is too thin to be organized.

    existing_draft = draft_structure(db, user.username, key)

    # The version is derived BEFORE the previous draft is discarded. Reading it afterwards
    # would hand a fresh generation the number the discarded one just released, and a
    # version number that can be reused cannot be used to tell two structures apart.
    version = _next_version(db, user.username, forms)
    if existing_draft is not None:
        discard_draft(db, user, key, existing_draft.id)

    structure = UserKnowledgeStructure(
        user_id=getattr(user, "id", None) or _user_id(db, user.username),
        username=user.username, course_id=key,
        version=version,
        status=STRUCTURE_DRAFT, source_mode=source_mode,
        source_file_ids=json.dumps(list(source_file_ids or [])[:MAX_SOURCE_FILES]),
        title=(title or f"{key} 知识结构")[:255],
        goal=(goal or "")[:120],
        point_count=total, chapter_count=len(chapters),
    )
    db.add(structure)
    db.flush()

    for chapter_index, chapter in enumerate(chapters):
        parent = KnowledgePoint(
            username=user.username, course_id=key, parent_id=None,
            title=chapter["title"], description=chapter.get("description") or "",
            order_index=chapter_index, level=1, structure_id=structure.id)
        db.add(parent)
        db.flush()
        for point_index, point in enumerate(chapter["points"]):
            db.add(KnowledgePoint(
                username=user.username, course_id=key, parent_id=parent.id,
                title=point["title"], description=point.get("description") or "",
                order_index=point_index, level=2, structure_id=structure.id,
                origin=point.get("origin") or ORIGIN_AI_INFERRED))
    db.commit()
    db.refresh(structure)
    return structure


def confirm(db, user, course_id, structure_id: int) -> dict:
    """Make a draft the structure the learner studies from.

    The version in use is SUPERSEDED, not deleted: its points keep existing so the
    progress rows that reference them stay valid, and the learner's record on a topic the
    new structure dropped is still there to read. Progress on topics that exist in both is
    copied forward, so confirming a regenerated structure does not cost the learner what
    they had already learned.
    """
    from models import UserKnowledgeStructure

    key, forms = _scope_forms(course_id)
    structure = (db.query(UserKnowledgeStructure)
                 .filter(UserKnowledgeStructure.id == structure_id,
                         UserKnowledgeStructure.username == user.username,
                         UserKnowledgeStructure.course_id.in_(sorted(forms)))
                 .first())
    if structure is None:
        raise KnowledgeStructureError("草稿不存在。", 404)
    if structure.status != STRUCTURE_DRAFT:
        raise KnowledgeStructureError("这份知识结构已经生效，不需要再次确认。", 409)

    old_active = active_structure(db, user.username, key)
    old_points = _points(db, user.username, forms, old_active.id) if old_active else []
    new_points = _points(db, user.username, forms, structure.id)
    if not new_points:
        raise KnowledgeStructureError("草稿里没有知识点，无法使用。")

    now = datetime.utcnow()
    carry = _carry_progress(db, user.username,
                            getattr(user, "id", None) or _user_id(db, user.username),
                            old_points, new_points)

    if old_active is not None:
        old_active.status = STRUCTURE_SUPERSEDED
        old_active.superseded_at = now
    structure.status = STRUCTURE_ACTIVE
    structure.confirmed_at = now
    db.commit()
    db.refresh(structure)
    return {"structure": _structure_view(structure), "progress_carried": carry}


def discard_draft(db, user, course_id, structure_id: int) -> None:
    """Delete a DRAFT and its generated points.

    Only a draft may be discarded, and a draft has never been studied from — no progress
    row can reference its points, because progress is only ever written against the
    structure the learner is working in. That is what makes this the one deletion in this
    module that cannot cost anybody anything.
    """
    from models import KnowledgePoint, UserKnowledgeStructure

    key, forms = _scope_forms(course_id)
    structure = (db.query(UserKnowledgeStructure)
                 .filter(UserKnowledgeStructure.id == structure_id,
                         UserKnowledgeStructure.username == user.username,
                         UserKnowledgeStructure.course_id.in_(sorted(forms)))
                 .first())
    if structure is None:
        raise KnowledgeStructureError("草稿不存在。", 404)
    if structure.status != STRUCTURE_DRAFT:
        raise KnowledgeStructureError("正在使用的知识结构不能删除。", 409)

    db.query(KnowledgePoint).filter(
        KnowledgePoint.username == user.username,
        KnowledgePoint.structure_id == structure.id,
    ).delete(synchronize_session=False)
    db.delete(structure)
    db.commit()


# ------------------------------------------------------------------ draft edits

def _draft_point(db, username, forms, structure_id, point_id):
    from models import KnowledgePoint
    return (db.query(KnowledgePoint)
            .filter(KnowledgePoint.id == point_id,
                    KnowledgePoint.username == username,
                    KnowledgePoint.structure_id == structure_id,
                    KnowledgePoint.course_id.in_(sorted(forms)))
            .first())


def _require_draft(db, user, course_id, structure_id: int):
    from models import UserKnowledgeStructure
    key, forms = _scope_forms(course_id)
    structure = (db.query(UserKnowledgeStructure)
                 .filter(UserKnowledgeStructure.id == structure_id,
                         UserKnowledgeStructure.username == user.username,
                         UserKnowledgeStructure.course_id.in_(sorted(forms)))
                 .first())
    if structure is None:
        raise KnowledgeStructureError("草稿不存在。", 404)
    if structure.status != STRUCTURE_DRAFT:
        raise KnowledgeStructureError("只能修改尚未使用的草稿。", 409)
    return key, forms, structure


def _refresh_counts(db, username, forms, structure) -> None:
    points = _points(db, username, forms, structure.id)
    structure.point_count = len([point for point in points if point.parent_id is not None])
    structure.chapter_count = len([point for point in points if point.parent_id is None])


def rename_point(db, user, course_id, structure_id: int, point_id: int, title: str) -> dict:
    title = (title or "").strip()
    if not title:
        raise KnowledgeStructureError("知识点名称不能为空。")
    key, forms, structure = _require_draft(db, user, course_id, structure_id)
    point = _draft_point(db, user.username, forms, structure.id, point_id)
    if point is None:
        raise KnowledgeStructureError("知识点不存在。", 404)
    point.title = title[:255]
    point.updated_at = datetime.utcnow()
    db.commit()
    return _structure_view(structure)


def delete_point(db, user, course_id, structure_id: int, point_id: int) -> dict:
    from models import KnowledgePoint

    key, forms, structure = _require_draft(db, user, course_id, structure_id)
    point = _draft_point(db, user.username, forms, structure.id, point_id)
    if point is None:
        raise KnowledgeStructureError("知识点不存在。", 404)
    if point.parent_id is None:
        # Deleting a chapter takes its points with it, so it is removed only when the
        # chapter is empty — the alternative is a chapter deletion that silently discards
        # a dozen points the learner never saw disappear.
        remaining = (db.query(KnowledgePoint)
                     .filter(KnowledgePoint.parent_id == point.id,
                             KnowledgePoint.structure_id == structure.id)
                     .count())
        if remaining:
            raise KnowledgeStructureError("这一章还有知识点，请先删除或移动它们。")
    db.delete(point)
    db.flush()
    _refresh_counts(db, user.username, forms, structure)
    db.commit()
    return _structure_view(structure)


def move_point(db, user, course_id, structure_id: int, point_id: int, chapter_id: int) -> dict:
    key, forms, structure = _require_draft(db, user, course_id, structure_id)
    point = _draft_point(db, user.username, forms, structure.id, point_id)
    if point is None:
        raise KnowledgeStructureError("知识点不存在。", 404)
    if point.parent_id is None:
        raise KnowledgeStructureError("章节本身不能移动到其他章节下。")
    chapter = _draft_point(db, user.username, forms, structure.id, chapter_id)
    if chapter is None or chapter.parent_id is not None:
        raise KnowledgeStructureError("目标章节不存在。", 404)
    point.parent_id = chapter.id
    point.order_index = len([child for child in _points(db, user.username, forms, structure.id)
                             if child.parent_id == chapter.id and child.id != point.id])
    point.updated_at = datetime.utcnow()
    db.commit()
    return _structure_view(structure)


def add_point(db, user, course_id, structure_id: int, chapter_id: int, title: str) -> dict:
    from models import KnowledgePoint

    title = (title or "").strip()
    if not title:
        raise KnowledgeStructureError("知识点名称不能为空。")
    key, forms, structure = _require_draft(db, user, course_id, structure_id)
    chapter = _draft_point(db, user.username, forms, structure.id, chapter_id)
    if chapter is None or chapter.parent_id is not None:
        raise KnowledgeStructureError("目标章节不存在。", 404)
    order = len([child for child in _points(db, user.username, forms, structure.id)
                 if child.parent_id == chapter.id])
    db.add(KnowledgePoint(
        username=user.username, course_id=chapter.course_id, parent_id=chapter.id,
        title=title[:255], description="", order_index=order, level=2,
        structure_id=structure.id, origin=ORIGIN_AI_INFERRED))
    db.flush()
    _refresh_counts(db, user.username, forms, structure)
    db.commit()
    return _structure_view(structure)
