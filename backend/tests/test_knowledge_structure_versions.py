"""USER+COURSE knowledge structures: sources, drafts, versions, progress safety.

The structure a learner studies from is their OWN — two learners on 数据结构 may each build
a tree from their own materials, and neither generation may touch the other's points or
progress. Two properties carry most of this file:

  * a generation writes a DRAFT and changes nothing the learner is currently studying from
  * switching versions must never silently erase a learning record

Both are asserted against stored rows, not against response bodies, because a response that
claims progress was kept is not evidence that it was.
"""
import pytest

from learning.spaces.course_learning import knowledge_structure as ks
from models import (CourseLearningPreference, KnowledgePoint, MaterialChunk, StudyMaterial,
                    User, UserKnowledgeProgress, UserKnowledgeStructure)

COURSE = "数据结构"
COURSE_B = "操作系统"


def make_user(db, username) -> User:
    user = User(username=username, hashed_password="x", grade="freshman", major="cs")
    db.add(user)
    db.commit()
    return user


def attach_course(db, user, course_id):
    db.add(CourseLearningPreference(username=user.username, course_id=course_id,
                                    display_name=course_id, mastery_level="",
                                    learning_goal=""))
    db.commit()


def make_material(db, user, course_id, filename, chunks=2) -> StudyMaterial:
    material = StudyMaterial(
        username=user.username, course_id=course_id, subject_key=course_id,
        subject=course_id, scope_type="course", file_type="pdf",
        original_filename=filename, file_size=10, file_path=f"/tmp/{filename}",
        extracted_text="x", summary="s")
    db.add(material)
    db.flush()
    for index in range(chunks):
        db.add(MaterialChunk(
            material_id=material.id, username=user.username, course_id=course_id,
            subject_key=course_id, subject=course_id, chunk_index=index,
            chunk_text=f"{filename} 片段 {index}", chunk_summary=f"{filename} 摘要 {index}",
            source_filename=filename))
    db.commit()
    return material


def generated(*chapters, origin=ks.ORIGIN_AI_INFERRED):
    """A model answer in the shape the generator parses, without calling a provider.

    ``origin`` is set here because the generators set it too — a fixture that skipped it
    would be testing a shape the real code never produces.
    """
    return [{"title": title, "points": [{"title": point, "description": "",
                                         "source_hint": hint, "origin": origin}
                                        for point, hint in points]}
            for title, points in chapters]


SAMPLE = generated(
    ("第1章 绪论", [("数据结构基本概念", "讲义.pdf"), ("算法与复杂度", "讲义.pdf")]),
    ("第2章 线性表", [("顺序表", "讲义.pdf"), ("链表", "")]),
)

SAMPLE_V2 = generated(
    ("第1章 绪论", [("数据结构基本概念", "讲义.pdf"), ("算法与复杂度", "讲义.pdf")]),
    ("第2章 线性表", [("顺序表", "讲义.pdf"), ("链表", "讲义.pdf")]),
    ("第3章 树与二叉树", [("二叉树的遍历", "讲义.pdf")]),
)


@pytest.fixture
def answers(monkeypatch):
    """The model's answer, chosen per test — no provider is ever called."""
    calls = {"material": [], "ai": []}

    def fake_material(db, user, course_id, material_ids):
        calls["material"].append(list(material_ids))
        return SAMPLE

    def fake_ai(db, user, course_id, goal="", requirement=""):
        calls["ai"].append({"goal": goal, "requirement": requirement})
        return SAMPLE

    monkeypatch.setattr(ks, "generate_from_materials", fake_material)
    monkeypatch.setattr(ks, "generate_from_ai", fake_ai)
    return calls


def point_titles(db, username, course_id, structure_id):
    return {point.title for point in ks._points(
        db, username, ks._scope_forms(course_id)[1], structure_id)}


# ══════════════════════════════════════════════════ FILE MODE


def test_a_course_with_no_material_cannot_generate_from_files(db_session):
    """The picker is not a formality: generating from files with no file is refused."""
    user = make_user(db_session, "ks_fileless")
    attach_course(db_session, user, COURSE)
    with pytest.raises(ks.KnowledgeStructureError) as exc:
        ks.generate_from_materials(db_session, user, COURSE, [7])
    assert "资料" in str(exc.value)


def test_uploaded_materials_become_selectable(db_session):
    user = make_user(db_session, "ks_picker")
    attach_course(db_session, user, COURSE)
    first = make_material(db_session, user, COURSE, "讲义.pdf")
    second = make_material(db_session, user, COURSE, "chapter4_Tree.pdf")

    names, lines, materials = ks._material_lines(
        db_session, user.username, COURSE, [first.id, second.id])
    assert names == ["讲义.pdf", "chapter4_Tree.pdf"]
    assert len(lines) == 4
    assert {material.id for material in materials} == {first.id, second.id}


def test_a_single_selected_file_generates_a_structure(db_session, monkeypatch):
    """ONE file is enough — the picker does not require the whole library."""
    from models import MaterialChunk as Chunk

    user = make_user(db_session, "ks_single")
    attach_course(db_session, user, COURSE)
    material = make_material(db_session, user, COURSE, "讲义.pdf")
    asked = {}

    def fake_call(db, user, course_id, material_ids, system_prompt, user_prompt):
        asked["prompt"] = user_prompt
        return ('{"chapters": [{"title": "第一章", "points": '
                '[{"title": "顺序表", "source_hint": "讲义.pdf"}]}]}')

    monkeypatch.setattr(ks, "_call_ai", fake_call)
    chapters = ks.generate_from_materials(db_session, user, COURSE, [material.id])

    assert len(chapters) == 1
    assert chapters[0]["points"][0]["origin"] == ks.ORIGIN_SOURCE_EXTRACTED
    # The prompt carried THIS file's own text, which is what makes it grounded.
    assert "讲义.pdf" in asked["prompt"]
    assert db_session.query(Chunk).filter(Chunk.material_id == material.id).count() == 2


def test_several_files_generate_together_and_the_source_ids_are_recorded(db_session):
    user = make_user(db_session, "ks_multi")
    attach_course(db_session, user, COURSE)
    first = make_material(db_session, user, COURSE, "讲义.pdf")
    second = make_material(db_session, user, COURSE, "chapter4_Tree.pdf")

    structure = ks.create_draft(
        db_session, user, COURSE, source_mode=ks.SOURCE_MODE_SELECTED_MATERIALS,
        chapters=SAMPLE, source_file_ids=[first.id, second.id])

    view = ks._structure_view(structure)
    assert view["source_mode"] == "selected_materials"
    assert view["source_file_ids"] == [first.id, second.id]


def test_a_point_extracted_from_a_named_file_is_distinguished_from_an_inferred_one(db_session, monkeypatch):
    """Provenance is decided by this module, not by the model's self-report."""
    user = make_user(db_session, "ks_origin")
    attach_course(db_session, user, COURSE)
    material = make_material(db_session, user, COURSE, "讲义.pdf")
    monkeypatch.setattr(ks, "_call_ai", lambda *a, **k: (
        '{"chapters": [{"title": "第1章 绪论", "points": ['
        '{"title": "数据结构基本概念", "source_hint": "讲义.pdf"},'
        '{"title": "算法与复杂度", "source_hint": "讲义.pdf"}]},'
        '{"title": "第2章 线性表", "points": ['
        '{"title": "顺序表", "source_hint": "讲义.pdf"},'
        '{"title": "链表", "source_hint": ""}]}]}'))

    chapters = ks.generate_from_materials(db_session, user, COURSE, [material.id])
    origins = {point["title"]: point["origin"]
               for chapter in chapters for point in chapter["points"]}
    assert set(origins) == {"数据结构基本概念", "算法与复杂度", "顺序表", "链表"}
    assert origins["链表"] == ks.ORIGIN_AI_INFERRED


def test_a_material_point_must_name_a_file_that_was_actually_selected(db_session, monkeypatch):
    user = make_user(db_session, "ks_origin_guard")
    attach_course(db_session, user, COURSE)
    material = make_material(db_session, user, COURSE, "讲义.pdf")
    monkeypatch.setattr(ks, "_call_ai", lambda *a, **k: '{"chapters": [{"title": "第一章", '
        '"points": [{"title": "顺序表", "source_hint": "别人的教材.pdf"}]}]}')

    chapters = ks.generate_from_materials(db_session, user, COURSE, [material.id])
    assert chapters[0]["points"][0]["origin"] == ks.ORIGIN_AI_INFERRED


# ══════════════════════════════════════════════════ AI MODE


def test_ai_generation_needs_no_material_at_all(db_session, answers):
    user = make_user(db_session, "ks_ai")
    attach_course(db_session, user, COURSE)

    chapters = ks.generate_from_ai(db_session, user, COURSE, goal="考研")
    assert answers["ai"][0]["goal"] == "考研"
    assert [chapter["title"] for chapter in chapters] == ["第1章 绪论", "第2章 线性表"]
    assert all(point["origin"] == ks.ORIGIN_AI_INFERRED
               for chapter in chapters for point in chapter["points"])


def test_an_ai_structure_is_recorded_as_ai_generated(db_session, answers):
    user = make_user(db_session, "ks_ai_mode")
    attach_course(db_session, user, COURSE)
    structure = ks.create_draft(
        db_session, user, COURSE, source_mode=ks.SOURCE_MODE_AI_GENERATED,
        chapters=ks.generate_from_ai(db_session, user, COURSE))

    assert ks._structure_view(structure)["source_mode"] == "ai_generated"
    assert ks._structure_view(structure)["source_file_ids"] == []


# ══════════════════════════════════════════════════ DRAFT ≠ ACTIVE


def test_a_generated_structure_is_only_a_draft(db_session):
    user = make_user(db_session, "ks_draft")
    attach_course(db_session, user, COURSE)
    structure = ks.create_draft(db_session, user, COURSE,
                               source_mode=ks.SOURCE_MODE_SELECTED_MATERIALS,
                               chapters=SAMPLE)

    state = ks.describe(db_session, user.username, COURSE)
    assert state["display"] == "draft"
    assert state["active"] is None
    assert state["draft"]["id"] == structure.id
    assert state["draft"]["version"] == 1
    # Nothing is active, so nothing is what the learner studies from yet.
    assert ks.active_structure(db_session, user.username, COURSE) is None


def test_the_active_points_reader_ignores_an_unconfirmed_draft(db_session):
    """The reader every other course surface uses must not see draft points as the course."""
    from main import _knowledge_point_version_filter

    user = make_user(db_session, "ks_reader")
    attach_course(db_session, user, COURSE)
    ks.create_draft(db_session, user, COURSE,
                    source_mode=ks.SOURCE_MODE_AI_GENERATED, chapters=SAMPLE)

    visible = (db_session.query(KnowledgePoint)
               .filter(KnowledgePoint.username == user.username,
                       _knowledge_point_version_filter(db_session, user.username, COURSE))
               .all())
    assert visible == []


def test_confirming_a_draft_makes_it_the_structure_in_use(db_session):
    user = make_user(db_session, "ks_confirm")
    attach_course(db_session, user, COURSE)
    structure = ks.create_draft(db_session, user, COURSE,
                               source_mode=ks.SOURCE_MODE_AI_GENERATED, chapters=SAMPLE)

    ks.confirm(db_session, user, COURSE, structure.id)

    state = ks.describe(db_session, user.username, COURSE)
    assert state["display"] == "active"
    assert state["active"]["id"] == structure.id
    assert state["draft"] is None
    assert state["active"]["point_count"] == 4
    assert state["active"]["chapter_count"] == 2
    assert [chapter["title"] for chapter in state["chapters"]] == ["第1章 绪论", "第2章 线性表"]


def test_a_confirmed_draft_cannot_be_confirmed_twice(db_session):
    user = make_user(db_session, "ks_double")
    attach_course(db_session, user, COURSE)
    structure = ks.create_draft(db_session, user, COURSE,
                               source_mode=ks.SOURCE_MODE_AI_GENERATED, chapters=SAMPLE)
    ks.confirm(db_session, user, COURSE, structure.id)

    with pytest.raises(ks.KnowledgeStructureError) as exc:
        ks.confirm(db_session, user, COURSE, structure.id)
    assert exc.value.status_code == 409


# ══════════════════════════════════════════════════ VERSIONS


def test_regenerating_produces_a_new_draft_and_leaves_the_active_version_alone(db_session):
    user = make_user(db_session, "ks_regen")
    attach_course(db_session, user, COURSE)
    first = ks.create_draft(db_session, user, COURSE,
                            source_mode=ks.SOURCE_MODE_AI_GENERATED, chapters=SAMPLE)
    ks.confirm(db_session, user, COURSE, first.id)

    second = ks.create_draft(db_session, user, COURSE,
                             source_mode=ks.SOURCE_MODE_AI_GENERATED, chapters=SAMPLE_V2)

    state = ks.describe(db_session, user.username, COURSE)
    assert state["display"] == "draft"
    assert state["active"]["id"] == first.id
    assert state["active"]["version"] == 1
    assert state["draft"]["id"] == second.id
    assert state["draft"]["version"] == 2
    # The v1 tree is still there, whole.
    assert point_titles(db_session, user.username, COURSE, first.id) == {
        "第1章 绪论", "第2章 线性表", "数据结构基本概念", "算法与复杂度", "顺序表", "链表"}


def test_cancelling_a_draft_leaves_the_active_version_untouched(db_session):
    user = make_user(db_session, "ks_cancel")
    attach_course(db_session, user, COURSE)
    first = ks.create_draft(db_session, user, COURSE,
                            source_mode=ks.SOURCE_MODE_AI_GENERATED, chapters=SAMPLE)
    ks.confirm(db_session, user, COURSE, first.id)
    second = ks.create_draft(db_session, user, COURSE,
                             source_mode=ks.SOURCE_MODE_AI_GENERATED, chapters=SAMPLE_V2)

    ks.discard_draft(db_session, user, COURSE, second.id)

    state = ks.describe(db_session, user.username, COURSE)
    assert state["display"] == "active"
    assert state["active"]["id"] == first.id
    assert state["draft"] is None
    assert point_titles(db_session, user.username, COURSE, first.id)  # still intact


def test_confirming_a_new_version_switches_the_active_one_and_keeps_the_old(db_session):
    user = make_user(db_session, "ks_switch")
    attach_course(db_session, user, COURSE)
    first = ks.create_draft(db_session, user, COURSE,
                            source_mode=ks.SOURCE_MODE_AI_GENERATED, chapters=SAMPLE)
    ks.confirm(db_session, user, COURSE, first.id)
    second = ks.create_draft(db_session, user, COURSE,
                             source_mode=ks.SOURCE_MODE_AI_GENERATED, chapters=SAMPLE_V2)
    ks.confirm(db_session, user, COURSE, second.id)

    rows = {row.id: row for row in db_session.query(UserKnowledgeStructure).all()}
    assert rows[first.id].status == "superseded"
    assert rows[first.id].superseded_at is not None
    assert rows[second.id].status == "active"

    visible = (db_session.query(KnowledgePoint)
               .filter(KnowledgePoint.structure_id == second.id).count())
    assert visible == 8
    # The superseded version's points were not deleted with it.
    assert (db_session.query(KnowledgePoint)
            .filter(KnowledgePoint.structure_id == first.id).count()) == 6


def test_the_live_reader_follows_the_switch_instead_of_showing_both_versions(db_session):
    from main import _knowledge_point_version_filter

    user = make_user(db_session, "ks_live_reader")
    attach_course(db_session, user, COURSE)
    first = ks.create_draft(db_session, user, COURSE,
                            source_mode=ks.SOURCE_MODE_AI_GENERATED, chapters=SAMPLE)
    ks.confirm(db_session, user, COURSE, first.id)
    second = ks.create_draft(db_session, user, COURSE,
                             source_mode=ks.SOURCE_MODE_AI_GENERATED, chapters=SAMPLE_V2)
    ks.confirm(db_session, user, COURSE, second.id)

    visible = {point.title for point in db_session.query(KnowledgePoint).filter(
        KnowledgePoint.username == user.username,
        _knowledge_point_version_filter(db_session, user.username, COURSE)).all()}
    assert "二叉树的遍历" in visible
    assert "第3章 树与二叉树" in visible
    assert len(visible) == 8


def test_an_active_structure_cannot_be_discarded(db_session):
    user = make_user(db_session, "ks_no_discard")
    attach_course(db_session, user, COURSE)
    structure = ks.create_draft(db_session, user, COURSE,
                               source_mode=ks.SOURCE_MODE_AI_GENERATED, chapters=SAMPLE)
    ks.confirm(db_session, user, COURSE, structure.id)

    with pytest.raises(ks.KnowledgeStructureError) as exc:
        ks.discard_draft(db_session, user, COURSE, structure.id)
    assert exc.value.status_code == 409
    assert ks.active_structure(db_session, user.username, COURSE).id == structure.id


# ══════════════════════════════════════════════════ PROGRESS SAFETY


def _master(db, user, point_id, score=80, status="mastered"):
    db.add(UserKnowledgeProgress(
        user_id=user.id, username=user.username, course_id=COURSE,
        knowledge_point_id=point_id, knowledge_point_title="x",
        mastery_score=score, status=status, practice_count=3))
    db.commit()


def test_switching_versions_carries_the_progress_of_surviving_points(db_session):
    user = make_user(db_session, "ks_carry")
    attach_course(db_session, user, COURSE)
    first = ks.create_draft(db_session, user, COURSE,
                            source_mode=ks.SOURCE_MODE_AI_GENERATED, chapters=SAMPLE)
    ks.confirm(db_session, user, COURSE, first.id)

    mastered = (db_session.query(KnowledgePoint)
                .filter(KnowledgePoint.username == user.username,
                        KnowledgePoint.structure_id == first.id,
                        KnowledgePoint.title == "顺序表").one())
    _master(db_session, user, mastered.id, score=80, status="mastered")

    second = ks.create_draft(db_session, user, COURSE,
                             source_mode=ks.SOURCE_MODE_AI_GENERATED, chapters=SAMPLE_V2)
    preview = ks.carry_over_preview(db_session, user.username, COURSE)
    assert preview["has_progress"] is True
    assert preview["progressed_points"] == 1
    assert preview["matched_point_count"] >= 4
    # The number the learner is shown is about RECORDED topics, not matched titles: 顺序表 is
    # the only one with a record, and it survives.
    assert preview["matched_progressed_points"] == 1
    assert preview["unmatched_progressed_points"] == 0

    result = ks.confirm(db_session, user, COURSE, second.id)
    # ONE row was carried: only 顺序表 had a record. The other matching titles had nothing
    # to carry, and a point with no history correctly starts with none.
    assert result["progress_carried"]["carried"] == 1
    assert result["progress_carried"]["kept_on_previous_version"] == 0

    new_point = (db_session.query(KnowledgePoint)
                 .filter(KnowledgePoint.username == user.username,
                         KnowledgePoint.structure_id == second.id,
                         KnowledgePoint.title == "顺序表").one())
    moved = (db_session.query(UserKnowledgeProgress)
             .filter(UserKnowledgeProgress.username == user.username,
                     UserKnowledgeProgress.knowledge_point_id == new_point.id).one())
    assert moved.mastery_score == 80
    assert moved.status == "mastered"
    assert moved.practice_count == 3

    # ... and the row it came from is still there, on the version that was superseded.
    original = (db_session.query(UserKnowledgeProgress)
                .filter(UserKnowledgeProgress.username == user.username,
                        UserKnowledgeProgress.knowledge_point_id == mastered.id).one())
    assert original.mastery_score == 80 and original.status == "mastered"


def test_progress_on_a_dropped_topic_is_kept_rather_than_cleared(db_session):
    """A topic the new structure does not contain must not silently lose its record."""
    user = make_user(db_session, "ks_dropped_topic")
    attach_course(db_session, user, COURSE)
    first = ks.create_draft(db_session, user, COURSE,
                            source_mode=ks.SOURCE_MODE_AI_GENERATED, chapters=SAMPLE)
    ks.confirm(db_session, user, COURSE, first.id)

    only_in_v1 = (db_session.query(KnowledgePoint)
                  .filter(KnowledgePoint.username == user.username,
                          KnowledgePoint.structure_id == first.id,
                          KnowledgePoint.title == "链表").one())
    _master(db_session, user, only_in_v1.id, score=60, status="learning")

    shorter = generated(("第1章 绪论", [("数据结构基本概念", ""), ("算法与复杂度", "")]))
    second = ks.create_draft(db_session, user, COURSE,
                             source_mode=ks.SOURCE_MODE_AI_GENERATED, chapters=shorter)
    preview = ks.carry_over_preview(db_session, user.username, COURSE)
    assert preview["unmatched_active_points"] > 0

    result = ks.confirm(db_session, user, COURSE, second.id)
    assert result["progress_carried"]["kept_on_previous_version"] > 0

    survivor = (db_session.query(UserKnowledgeProgress)
                .filter(UserKnowledgeProgress.username == user.username,
                        UserKnowledgeProgress.knowledge_point_id == only_in_v1.id).one())
    assert survivor.mastery_score == 60 and survivor.status == "learning"


def test_progress_and_points_never_cross_between_two_learners(db_session):
    alice = make_user(db_session, "ks_alice")
    bob = make_user(db_session, "ks_bob")
    attach_course(db_session, alice, COURSE)
    attach_course(db_session, bob, COURSE)

    alice_structure = ks.create_draft(db_session, alice, COURSE,
                                      source_mode=ks.SOURCE_MODE_AI_GENERATED,
                                      chapters=SAMPLE)
    ks.confirm(db_session, alice, COURSE, alice_structure.id)
    alice_point = (db_session.query(KnowledgePoint)
                   .filter(KnowledgePoint.username == "ks_alice",
                           KnowledgePoint.title == "顺序表").one())
    _master(db_session, alice, alice_point.id, score=90, status="mastered")

    # Bob generates his own, from a DIFFERENT source, and confirms it.
    bob_structure = ks.create_draft(
        db_session, bob, COURSE, source_mode=ks.SOURCE_MODE_AI_GENERATED,
        chapters=generated(("第一章 引论", [("进程与线程", "")])))
    ks.confirm(db_session, bob, COURSE, bob_structure.id)

    assert ks.active_structure(db_session, "ks_alice", COURSE).id == alice_structure.id
    assert ks.active_structure(db_session, "ks_bob", COURSE).id == bob_structure.id
    assert point_titles(db_session, "ks_alice", COURSE, alice_structure.id) != \
        point_titles(db_session, "ks_bob", COURSE, bob_structure.id)

    # Alice's progress is exactly where she left it — Bob's generation did not touch it.
    still_there = (db_session.query(UserKnowledgeProgress)
                   .filter(UserKnowledgeProgress.username == "ks_alice",
                           UserKnowledgeProgress.knowledge_point_id == alice_point.id).one())
    assert still_there.mastery_score == 90 and still_there.status == "mastered"
    # ... and Bob has not inherited it.
    assert (db_session.query(UserKnowledgeProgress)
            .filter(UserKnowledgeProgress.username == "ks_bob").count()) == 0


def test_alice_generating_in_her_own_course_cannot_touch_bobs_course(db_session):
    alice = make_user(db_session, "ks_scope_a")
    bob = make_user(db_session, "ks_scope_b")
    attach_course(db_session, alice, COURSE)
    attach_course(db_session, bob, COURSE_B)

    bob_structure = ks.create_draft(
        db_session, bob, COURSE_B, source_mode=ks.SOURCE_MODE_AI_GENERATED,
        chapters=generated(("第一章 引论", [("进程与线程", "")])))
    ks.confirm(db_session, bob, COURSE_B, bob_structure.id)

    ks.create_draft(db_session, alice, COURSE,
                    source_mode=ks.SOURCE_MODE_AI_GENERATED, chapters=SAMPLE)

    assert ks.describe(db_session, "ks_scope_b", COURSE_B)["active"]["id"] == bob_structure.id
    assert ks.describe(db_session, "ks_scope_b", COURSE_B)["draft"] is None


# ══════════════════════════════════════════════════ DRAFT EDITS


def test_a_draft_point_can_be_renamed_and_removed(db_session):
    user = make_user(db_session, "ks_edit")
    attach_course(db_session, user, COURSE)
    structure = ks.create_draft(db_session, user, COURSE,
                               source_mode=ks.SOURCE_MODE_AI_GENERATED, chapters=SAMPLE)
    point = (db_session.query(KnowledgePoint)
             .filter(KnowledgePoint.structure_id == structure.id,
                     KnowledgePoint.title == "链表").one())

    ks.rename_point(db_session, user, COURSE, structure.id, point.id, "单链表与双链表")
    db_session.refresh(point)
    assert point.title == "单链表与双链表"

    ks.delete_point(db_session, user, COURSE, structure.id, point.id)
    remaining = point_titles(db_session, user.username, COURSE, structure.id)
    assert "单链表与双链表" not in remaining
    db_session.refresh(structure)
    assert structure.point_count == 3


def test_a_point_can_be_moved_to_another_chapter(db_session):
    user = make_user(db_session, "ks_move")
    attach_course(db_session, user, COURSE)
    structure = ks.create_draft(db_session, user, COURSE,
                               source_mode=ks.SOURCE_MODE_AI_GENERATED, chapters=SAMPLE)
    chapters = {chapter.title: chapter for chapter in db_session.query(KnowledgePoint)
                .filter(KnowledgePoint.structure_id == structure.id,
                        KnowledgePoint.parent_id.is_(None)).all()}
    point = (db_session.query(KnowledgePoint)
             .filter(KnowledgePoint.structure_id == structure.id,
                     KnowledgePoint.title == "链表").one())

    ks.move_point(db_session, user, COURSE, structure.id, point.id,
                  chapters["第1章 绪论"].id)
    db_session.refresh(point)
    assert point.parent_id == chapters["第1章 绪论"].id


def test_an_active_structure_cannot_be_edited(db_session):
    user = make_user(db_session, "ks_edit_active")
    attach_course(db_session, user, COURSE)
    structure = ks.create_draft(db_session, user, COURSE,
                               source_mode=ks.SOURCE_MODE_AI_GENERATED, chapters=SAMPLE)
    ks.confirm(db_session, user, COURSE, structure.id)
    point = (db_session.query(KnowledgePoint)
             .filter(KnowledgePoint.structure_id == structure.id).first())

    with pytest.raises(ks.KnowledgeStructureError) as exc:
        ks.rename_point(db_session, user, COURSE, structure.id, point.id, "改个名字")
    assert exc.value.status_code == 409


def test_a_chapter_holding_points_cannot_be_deleted_out_from_under_them(db_session):
    user = make_user(db_session, "ks_chapter_delete")
    attach_course(db_session, user, COURSE)
    structure = ks.create_draft(db_session, user, COURSE,
                               source_mode=ks.SOURCE_MODE_AI_GENERATED, chapters=SAMPLE)
    chapter = (db_session.query(KnowledgePoint)
               .filter(KnowledgePoint.structure_id == structure.id,
                       KnowledgePoint.title == "第1章 绪论").one())

    with pytest.raises(ks.KnowledgeStructureError):
        ks.delete_point(db_session, user, COURSE, structure.id, chapter.id)


# ══════════════════════════════════════════════════ parsing + size guards


def test_the_model_answer_is_parsed_through_fences_and_prose():
    raw = '好的，这是结构：\n```json\n{"chapters": [{"title": "第一章", ' \
          '"points": [{"title": "顺序表"}]}]}\n```\n希望有帮助。'
    chapters = ks.parse_structure_json(raw)
    assert chapters[0]["title"] == "第一章"
    assert chapters[0]["points"][0]["title"] == "顺序表"


def test_a_module_style_answer_is_accepted_as_well_as_chapters():
    chapters = ks.parse_structure_json(
        '{"modules": [{"title": "第一章", "knowledge_points": [{"title": "顺序表"}]}]}')
    assert chapters[0]["points"][0]["title"] == "顺序表"


def test_an_answer_with_nothing_usable_is_an_error_not_an_empty_structure():
    with pytest.raises(ks.KnowledgeStructureError):
        ks.parse_structure_json('{"chapters": []}')


def test_a_chapter_of_fragments_is_trimmed_to_the_granularity_ceiling():
    """The ceiling is per chapter, so one runaway chapter cannot swallow the structure."""
    chapters = ks._chapter_payload([{
        "title": "第一章",
        "points": [{"title": f"碎片{index}"} for index in range(200)],
    }])
    assert len(chapters[0]["points"]) == ks.MAX_POINTS_PER_CHAPTER


def test_the_granularity_prompt_asks_for_less_than_the_hard_ceiling():
    """The asked-for range must be inside the enforced one, or the ask is unmeetable."""
    assert ks.PROMPT_MAX_CHAPTERS <= ks.MAX_CHAPTERS
    assert ks.PROMPT_MAX_POINTS_PER_CHAPTER <= ks.MAX_POINTS_PER_CHAPTER
    # ... and the total must be reachable, or it is a ceiling nothing can hit.
    assert ks.MAX_CHAPTERS * ks.MAX_POINTS_PER_CHAPTER > ks.MAX_POINTS_TOTAL


def test_a_structure_beyond_the_total_ceiling_is_refused_rather_than_stored(db_session):
    user = make_user(db_session, "ks_too_many")
    attach_course(db_session, user, COURSE)
    huge = [{"title": f"第{index}章",
             "points": [{"title": f"知识点{index}-{j}"}
                        for j in range(ks.MAX_POINTS_PER_CHAPTER)]}
            for index in range(ks.MAX_CHAPTERS)]
    assert len(huge) * ks.MAX_POINTS_PER_CHAPTER > ks.MAX_POINTS_TOTAL

    with pytest.raises(ks.KnowledgeStructureError) as exc:
        ks.create_draft(db_session, user, COURSE,
                        source_mode=ks.SOURCE_MODE_AI_GENERATED, chapters=huge)
    assert "过多" in str(exc.value)
    assert ks.draft_structure(db_session, user.username, COURSE) is None


def test_an_empty_structure_is_refused_instead_of_stored_as_nothing(db_session):
    user = make_user(db_session, "ks_empty")
    attach_course(db_session, user, COURSE)
    with pytest.raises(ks.KnowledgeStructureError):
        ks.create_draft(db_session, user, COURSE,
                        source_mode=ks.SOURCE_MODE_AI_GENERATED, chapters=[])
    assert ks.active_structure(db_session, user.username, COURSE) is None
    assert ks.draft_structure(db_session, user.username, COURSE) is None


def test_only_one_draft_is_kept_per_course(db_session, answers):
    """Three generations in a row leave ONE draft — the one being looked at."""
    user = make_user(db_session, "ks_one_draft")
    attach_course(db_session, user, COURSE)
    first = ks.create_draft(db_session, user, COURSE,
                            source_mode=ks.SOURCE_MODE_AI_GENERATED, chapters=SAMPLE)
    second = ks.create_draft(db_session, user, COURSE,
                             source_mode=ks.SOURCE_MODE_AI_GENERATED, chapters=SAMPLE_V2)

    drafts = (db_session.query(UserKnowledgeStructure)
              .filter(UserKnowledgeStructure.username == user.username,
                      UserKnowledgeStructure.status == ks.STRUCTURE_DRAFT).all())
    assert [row.id for row in drafts] == [second.id]
    assert (db_session.query(KnowledgePoint)
            .filter(KnowledgePoint.structure_id == first.id).count()) == 0
    # ... and the versions keep counting up, so a version number is never reused.
    assert second.version == first.version + 1


# ══════════════════════════════════════════════════ HTTP surface


def _course_client(client, db_session, username):
    from conftest import register_and_login

    register_and_login(client, username)
    user = db_session.query(User).filter(User.username == username).one()
    attach_course(db_session, user, COURSE)
    return user


def test_the_page_reads_an_empty_state_before_anything_is_generated(client, db_session):
    _course_client(client, db_session, "ks_http_empty")
    response = client.get(f"/course-learning/courses/{COURSE}/knowledge-structure")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["display"] == "none"
    assert body["active"] is None and body["draft"] is None
    assert body["chapters"] == []


def test_a_course_the_caller_does_not_have_is_a_404(client, db_session):
    _course_client(client, db_session, "ks_http_404")
    assert client.get(
        "/course-learning/courses/量子力学/knowledge-structure").status_code == 404


def test_generating_from_files_without_picking_any_is_refused(client, db_session):
    _course_client(client, db_session, "ks_http_nofile")
    response = client.post(
        f"/course-learning/courses/{COURSE}/knowledge-structure/generate",
        json={"source_mode": "selected_materials", "material_ids": []})
    assert response.status_code == 400
    assert "资料" in response.json()["detail"]


def test_the_full_generate_preview_confirm_cycle_over_http(client, db_session, answers):
    user = _course_client(client, db_session, "ks_http_cycle")
    base = f"/course-learning/courses/{COURSE}/knowledge-structure"

    generated_response = client.post(f"{base}/generate",
                                    json={"source_mode": "ai_generated", "goal": "考研"})
    assert generated_response.status_code == 200, generated_response.text
    body = generated_response.json()
    assert body["display"] == "draft"
    assert body["active"] is None
    assert body["draft"]["source_mode"] == "ai_generated"
    assert body["draft"]["point_count"] == 4
    assert body["draft"]["chapter_count"] == 2
    assert body["carry_over"]["available"] is True
    structure_id = body["draft"]["id"]

    # Reading again returns the same draft — nothing auto-confirmed it.
    assert client.get(base).json()["display"] == "draft"

    confirmed = client.post(f"{base}/{structure_id}/confirm")
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["structure"]["status"] == "active"

    after = client.get(base).json()
    assert after["display"] == "active"
    assert after["draft"] is None
    assert after["active"]["id"] == structure_id
    assert [chapter["title"] for chapter in after["chapters"]] == ["第1章 绪论", "第2章 线性表"]


def test_a_draft_can_be_discarded_over_http_and_the_active_one_survives(
        client, db_session, answers):
    user = _course_client(client, db_session, "ks_http_discard")
    base = f"/course-learning/courses/{COURSE}/knowledge-structure"
    first = client.post(f"{base}/generate",
                        json={"source_mode": "ai_generated"}).json()["draft"]["id"]
    client.post(f"{base}/{first}/confirm")

    second = client.post(f"{base}/generate",
                         json={"source_mode": "ai_generated"}).json()["draft"]["id"]
    assert client.delete(f"{base}/{second}").status_code == 204

    body = client.get(base).json()
    assert body["display"] == "active"
    assert body["active"]["id"] == first


def test_the_learners_own_files_are_what_generation_is_scoped_to(client, db_session, monkeypatch):
    """A material id the caller does not own cannot be named into a generation."""
    user = _course_client(client, db_session, "ks_http_scope")
    other = make_user(db_session, "ks_http_other")
    stranger_material = make_material(db_session, other, COURSE, "别人.pdf")

    response = client.post(
        f"/course-learning/courses/{COURSE}/knowledge-structure/generate",
        json={"source_mode": "selected_materials",
              "material_ids": [stranger_material.id]})
    assert response.status_code == 400
    assert ks.draft_structure(db_session, user.username, COURSE) is None


def test_draft_edits_are_rejected_on_a_structure_that_is_already_in_use(
        client, db_session, answers):
    user = _course_client(client, db_session, "ks_http_edit")
    base = f"/course-learning/courses/{COURSE}/knowledge-structure"
    structure_id = client.post(f"{base}/generate",
                               json={"source_mode": "ai_generated"}).json()["draft"]["id"]
    point_id = (db_session.query(KnowledgePoint)
                .filter(KnowledgePoint.structure_id == structure_id,
                        KnowledgePoint.title == "链表").one().id)
    assert client.patch(f"{base}/{structure_id}/points/{point_id}",
                        json={"title": "单链表与双链表"}).status_code == 200

    client.post(f"{base}/{structure_id}/confirm")
    assert client.patch(f"{base}/{structure_id}/points/{point_id}",
                        json={"title": "再改一次"}).status_code == 409


# ══════════════════════════════════════════════════ the generation contract


def test_the_reference_directory_is_the_one_the_app_serves():
    """The seed path is read directly (importing the app module would run its startup), so
    the two copies must be pinned together or they drift and AI generation silently loses the
    canonical course system."""
    import main

    assert ks._knowledge_map_seed_path("data_structure") == main._knowledge_map_seed_path("data_structure")
    assert ks._knowledge_map_seed_path("数据结构") == main._knowledge_map_seed_path("数据结构")


def test_a_course_the_build_publishes_gets_its_canonical_outline():
    """数据结构 is a 408 subject this product already ships a structure for — the model is
    asked to organize by it rather than invent one."""
    outline = ks._canonical_outline("data_structure")
    assert outline.startswith("- ")
    assert len(outline.splitlines()) >= 5


def test_a_course_the_build_does_not_publish_gets_no_invented_reference():
    assert ks._canonical_outline("量子力学导论") == ""


def test_the_answer_asked_for_fits_the_budget_it_is_given():
    """The ask and the ceiling have to agree: an answer longer than the budget comes back cut
    off mid-object, which is not a smaller structure — it is no structure at all."""
    worst_case_points = ks.PROMPT_MAX_CHAPTERS * ks.PROMPT_MAX_POINTS_PER_CHAPTER
    # ~25 output tokens per point (title + description + JSON punctuation) plus chapter lines.
    assert worst_case_points * 40 < ks.OUTPUT_TOKEN_BUDGET * 4


def test_generation_reserves_its_own_output_budget(db_session, monkeypatch):
    """A whole course structure is one long JSON object, so it does not ride the chat default."""
    from learning.spaces.course_learning import ai as course_ai

    seen = {}

    class Result:
        content = '{"chapters": [{"title": "第一章", "points": [{"title": "知识点"}]}]}'

    def fake_execute(db, user, capability, messages, **kwargs):
        seen["max_tokens"] = kwargs.get("max_tokens")
        seen["capability"] = capability
        return Result()

    monkeypatch.setattr(course_ai, "execute_course_ai", fake_execute)
    user = make_user(db_session, "ks_budget")
    attach_course(db_session, user, COURSE)

    ks.generate_from_ai(db_session, user, COURSE, goal="考研")
    assert seen["capability"] == "knowledge.structure"
    assert seen["max_tokens"] == ks.OUTPUT_TOKEN_BUDGET


def test_a_cut_off_answer_fails_rather_than_becoming_a_partial_structure():
    """Truncated JSON must NOT be half-recovered: a silently shorter course reads exactly like
    a complete one, and the learner would accept it believing it was the whole structure."""
    truncated = ('{"chapters": [{"title": "第一章", "points": [{"title": "数据结构基本概念"},'
                 ' {"title": "算法与复杂度"}]}, {"title": "第二章", "points": [{"title": "顺序')
    with pytest.raises(ks.KnowledgeStructureError) as exc:
        ks.parse_structure_json(truncated)
    assert exc.value.status_code == 502


def test_an_unusable_answer_is_asked_for_again_once(db_session, monkeypatch):
    """A provider that answered with prose succeeded as a call and failed as an answer. The
    learner asked for one structure; one retry is what turns a bad turn into a structure."""
    answers = iter(["这是第一章的内容……", '{"chapters": [{"title": "第一章", '
                                        '"points": [{"title": "顺序表"}]}]}'])
    calls = {"n": 0}

    def fake_call(*a, **k):
        calls["n"] += 1
        return next(answers)

    monkeypatch.setattr(ks, "_call_ai", fake_call)
    user = make_user(db_session, "ks_retry")
    attach_course(db_session, user, COURSE)

    chapters = ks.generate_from_ai(db_session, user, COURSE)
    assert chapters[0]["points"][0]["title"] == "顺序表"
    assert calls["n"] == 2


def test_two_unusable_answers_fail_instead_of_looping(db_session, monkeypatch):
    calls = {"n": 0}

    def fake_call(*a, **k):
        calls["n"] += 1
        return "还是说明文字，不是 JSON。"

    monkeypatch.setattr(ks, "_call_ai", fake_call)
    user = make_user(db_session, "ks_retry_twice")
    attach_course(db_session, user, COURSE)

    with pytest.raises(ks.KnowledgeStructureError) as exc:
        ks.generate_from_ai(db_session, user, COURSE)
    assert exc.value.status_code == 502
    assert calls["n"] == 2
    assert ks.draft_structure(db_session, user.username, COURSE) is None


def test_a_refusal_is_not_asked_again(db_session, monkeypatch):
    """No permission, no budget, a provider error — asking again buys the same refusal with the
    learner's credits."""
    from fastapi import HTTPException

    calls = {"n": 0}

    def refusing(*a, **k):
        calls["n"] += 1
        raise HTTPException(status_code=403, detail="AI capability unavailable")

    monkeypatch.setattr(ks, "_call_ai", refusing)
    user = make_user(db_session, "ks_refused")
    attach_course(db_session, user, COURSE)

    with pytest.raises(HTTPException) as exc:
        ks.generate_from_ai(db_session, user, COURSE)
    assert exc.value.status_code == 403
    assert calls["n"] == 1
