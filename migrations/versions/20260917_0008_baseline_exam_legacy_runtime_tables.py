"""baseline exam legacy runtime tables

Revision ID: 20260917_0008
Revises: 20260917_0007
Create Date: 2026-09-17

STEP7H5 gives the Exam Prep / CS408 RUNTIME schema a real Alembic baseline.

Until this revision, every Exam table was created by
``backend/database.py::ensure_*_schema()`` and by ``Base.metadata.create_all()`` at
startup — not by a migration. That is why a fresh deployment could not be produced from
``alembic upgrade head`` alone. This revision closes that gap for the Exam domain.

WHAT IS IN SCOPE — tables the Exam Prep request path actually reads or writes
------------------------------------------------------------------------------------
Derived empirically from the exam route handlers (not from a name pattern) plus the one
shared store the exam knowledge writer owns:

    exam_question_bank                    question bank (READ-ONLY content, 9333 rows)
    exam_practice_attempts                chapter practice sessions
    exam_wrong_questions                  exam wrong-answer projection
    exam_question_done_records            per-question done ledger
    exam_favorite_questions               favourites
    past_paper_attempts                   past paper attempts
    past_paper_wrong_questions            past paper wrong-answer projection
    exam_study_plan_settings              study plan settings
    exam_study_plan_chapter_practice       study plan chapter-practice ticks
    exam_study_plan_tasks                 study plan tasks
    ai_generated_questions                AI-generated questions
    user_knowledge_progress               SHARED STORE — the exam knowledge writer
    user_knowledge_review_settings        SHARED STORE — review interval policy

WHAT IS DELIBERATELY EXCLUDED
------------------------------------------------------------------------------------
``exam_favorite_questions_v2`` is a DEAD table (0 rows, 0 code references outside its own
model declaration and a cleanup script, no FK dependency). It is classified
DELETE-LATER and is **not** promoted to a canonical requirement by this migration —
being at "full table count" is not a goal.

SHARED tables owned by other spaces (``knowledge_points`` / ``knowledge_progress_events``
/ ``material_knowledge_links`` — course learning and the programming ontology) are NOT
baselined here; they belong to the wider legacy baseline, which is registered as
non-blocking debt in the STEP7H5 report.

SAFETY — ONE migration, TWO starting points
------------------------------------------------------------------------------------
A. fresh empty DB        -> every table below is created (with its model indexes)
B. legacy backend/app.db -> the tables already exist; they are LEFT INTACT. Only
                            missing model-declared columns / indexes are added.

Never DROP, never rebuild, never rewrite rows. No question row, no user row, and no
existing table definition is modified. Question bank content is untouched by
construction: this revision only emits DDL.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260917_0008"
down_revision: Union[str, None] = "20260917_0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (table, [(column_name, sa.Column)], [(index_name, [cols], unique)])
# Declared explicitly rather than derived from the live models so this migration is a
# frozen snapshot: a later model change must not silently rewrite history.
TABLES: tuple[tuple[str, tuple, tuple], ...] = (
    (
        "exam_question_bank",
        (
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("subject_key", sa.String(length=50), nullable=False),
            sa.Column("subject_name", sa.String(length=50), nullable=True),
            sa.Column("source_type", sa.String(length=30), nullable=False),
            sa.Column("visibility", sa.String(length=20), nullable=False),
            sa.Column("owner_username", sa.String(length=50), nullable=True),
            sa.Column("knowledge_point_id", sa.String(length=100), nullable=True),
            sa.Column("knowledge_point_name", sa.String(length=255), nullable=True),
            sa.Column("knowledge_point_path", sa.Text(), nullable=True),
            sa.Column("year", sa.Integer(), nullable=True),
            sa.Column("question_number", sa.Integer(), nullable=True),
            sa.Column("question_type", sa.String(length=30), nullable=False),
            sa.Column("stem", sa.Text(), nullable=False),
            sa.Column("options_json", sa.Text(), nullable=True),
            sa.Column("standard_answer", sa.Text(), nullable=True),
            sa.Column("analysis", sa.Text(), nullable=True),
            sa.Column("difficulty", sa.String(length=30), nullable=True),
            sa.Column("source_ref", sa.Text(), nullable=True),
            sa.Column("generation_mode", sa.String(length=30), nullable=True),
            sa.Column("quality_status", sa.String(length=20), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        ),
        (
            ("ix_exam_question_bank_id", ["id"], False),
            ("ix_exam_question_bank_source_type", ["source_type"], False),
            ("ix_exam_question_bank_subject_key", ["subject_key"], False),
        ),
    ),
    (
        "exam_practice_attempts",
        (
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("username", sa.String(length=50), nullable=False),
            sa.Column("subject_key", sa.String(length=50), nullable=False),
            sa.Column("practice_type", sa.String(length=30), nullable=False),
            sa.Column("source_type", sa.String(length=30), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("title", sa.String(length=255), nullable=True),
            sa.Column("knowledge_point_id", sa.String(length=100), nullable=True),
            sa.Column("knowledge_point_name", sa.String(length=255), nullable=True),
            sa.Column("knowledge_point_path", sa.Text(), nullable=True),
            sa.Column("year", sa.Integer(), nullable=True),
            sa.Column("question_ids_json", sa.Text(), nullable=True),
            sa.Column("answers_json", sa.Text(), nullable=True),
            sa.Column("result_json", sa.Text(), nullable=True),
            sa.Column("total_questions", sa.Integer(), nullable=False),
            sa.Column("correct_count", sa.Integer(), nullable=True),
            sa.Column("wrong_count", sa.Integer(), nullable=True),
            sa.Column("accuracy", sa.Float(), nullable=True),
            sa.Column("started_at", sa.DateTime(), nullable=True),
            sa.Column("submitted_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        ),
        (
            ("ix_exam_practice_attempts_id", ["id"], False),
            ("ix_exam_practice_attempts_username", ["username"], False),
        ),
    ),
    (
        "exam_wrong_questions",
        (
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("username", sa.String(length=50), nullable=False),
            sa.Column("subject_key", sa.String(length=50), nullable=False),
            sa.Column("question_bank_id", sa.Integer(), nullable=True),
            sa.Column("practice_attempt_id", sa.Integer(), nullable=True),
            sa.Column("source_type", sa.String(length=30), nullable=True),
            sa.Column("practice_type", sa.String(length=30), nullable=True),
            sa.Column("knowledge_point_id", sa.String(length=100), nullable=True),
            sa.Column("knowledge_point_name", sa.String(length=255), nullable=True),
            sa.Column("knowledge_point_path", sa.Text(), nullable=True),
            sa.Column("year", sa.Integer(), nullable=True),
            sa.Column("question_number", sa.Integer(), nullable=True),
            sa.Column("question_type", sa.String(length=30), nullable=True),
            sa.Column("stem_snapshot", sa.Text(), nullable=True),
            sa.Column("options_snapshot_json", sa.Text(), nullable=True),
            sa.Column("standard_answer_snapshot", sa.Text(), nullable=True),
            sa.Column("analysis_snapshot", sa.Text(), nullable=True),
            sa.Column("user_answer", sa.Text(), nullable=True),
            sa.Column("score", sa.Integer(), nullable=True),
            sa.Column("wrong_reason", sa.Text(), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("mastered", sa.Boolean(), nullable=False),
            sa.Column("review_count", sa.Integer(), nullable=False),
            sa.Column("resolved_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        ),
        (
            ("ix_exam_wrong_questions_id", ["id"], False),
            ("ix_exam_wrong_questions_subject_key", ["subject_key"], False),
            ("ix_exam_wrong_questions_username", ["username"], False),
        ),
    ),
    (
        "exam_question_done_records",
        (
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("username", sa.String(length=50), nullable=False),
            sa.Column("subject_key", sa.String(length=50), nullable=False),
            sa.Column("practice_type", sa.String(length=30), nullable=False),
            sa.Column("question_bank_id", sa.Integer(), nullable=True),
            sa.Column("ai_question_id", sa.Integer(), nullable=True),
            sa.Column("question_type", sa.String(length=30), nullable=True),
            sa.Column("user_answer", sa.Text(), nullable=True),
            sa.Column("correct_answer", sa.Text(), nullable=True),
            sa.Column("is_correct", sa.Boolean(), nullable=True),
            sa.Column("done_count", sa.Integer(), nullable=False),
            sa.Column("attempt_id", sa.Integer(), nullable=True),
            sa.Column("first_done_at", sa.DateTime(), nullable=True),
            sa.Column("last_done_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        ),
        (
            ("ix_exam_question_done_records_id", ["id"], False),
            ("ix_exam_question_done_records_subject_key", ["subject_key"], False),
            ("ix_exam_question_done_records_username", ["username"], False),
        ),
    ),
    (
        "exam_favorite_questions",
        (
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("username", sa.String(length=50), nullable=False),
            sa.Column("subject_key", sa.String(length=50), nullable=False),
            sa.Column("subject_name", sa.String(length=50), nullable=True),
            sa.Column("source", sa.String(length=50), nullable=False),
            sa.Column("source_question_id", sa.String(length=100), nullable=False),
            sa.Column("year", sa.Integer(), nullable=True),
            sa.Column("number", sa.Integer(), nullable=True),
            sa.Column("question_type", sa.String(length=30), nullable=True),
            sa.Column("stem", sa.Text(), nullable=True),
            sa.Column("options_json", sa.Text(), nullable=True),
            sa.Column("standard_answer", sa.Text(), nullable=True),
            sa.Column("knowledge_point_id", sa.String(length=100), nullable=True),
            sa.Column("knowledge_point_name", sa.String(length=255), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        ),
        (
            ("ix_exam_favorite_questions_id", ["id"], False),
            ("ix_exam_favorite_questions_source", ["source"], False),
            ("ix_exam_favorite_questions_subject_key", ["subject_key"], False),
            ("ix_exam_favorite_questions_username", ["username"], False),
        ),
    ),
    (
        "past_paper_attempts",
        (
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("username", sa.String(length=50), nullable=False),
            sa.Column("mode", sa.String(length=20), nullable=False),
            sa.Column("subject_key", sa.String(length=50), nullable=False),
            sa.Column("subject_name", sa.String(length=50), nullable=False),
            sa.Column("year", sa.Integer(), nullable=False),
            sa.Column("attempt_no", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("total_questions", sa.Integer(), nullable=False),
            sa.Column("choice_correct", sa.Integer(), nullable=True),
            sa.Column("big_avg_score", sa.Float(), nullable=True),
            sa.Column("total_score", sa.Integer(), nullable=True),
            sa.Column("max_score", sa.Integer(), nullable=True),
            sa.Column("wrong_count", sa.Integer(), nullable=True),
            sa.Column("answers_json", sa.Text(), nullable=True),
            sa.Column("result_json", sa.Text(), nullable=True),
            sa.Column("started_at", sa.DateTime(), nullable=True),
            sa.Column("submitted_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        ),
        (
            ("ix_past_paper_attempts_id", ["id"], False),
            ("ix_past_paper_attempts_username", ["username"], False),
        ),
    ),
    (
        "past_paper_wrong_questions",
        (
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("username", sa.String(length=50), nullable=False),
            sa.Column("subject_key", sa.String(length=50), nullable=False),
            sa.Column("source", sa.String(length=50), nullable=False),
            sa.Column("year", sa.Integer(), nullable=False),
            sa.Column("attempt_id", sa.Integer(), nullable=True),
            sa.Column("question_id", sa.String(length=100), nullable=False),
            sa.Column("question_number", sa.Integer(), nullable=False),
            sa.Column("question_type", sa.String(length=20), nullable=False),
            sa.Column("content", sa.Text(), nullable=True),
            sa.Column("options", sa.Text(), nullable=True),
            sa.Column("standard_answer", sa.Text(), nullable=True),
            sa.Column("user_answer", sa.Text(), nullable=True),
            sa.Column("score", sa.Integer(), nullable=True),
            sa.Column("wrong_reason", sa.Text(), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("mastered", sa.Boolean(), nullable=False),
            sa.Column("resolved_at", sa.DateTime(), nullable=True),
            sa.Column("reviewed_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        ),
        (
            ("ix_past_paper_wrong_questions_id", ["id"], False),
            ("ix_past_paper_wrong_questions_source", ["source"], False),
            ("ix_past_paper_wrong_questions_subject_key", ["subject_key"], False),
            ("ix_past_paper_wrong_questions_username", ["username"], False),
        ),
    ),
    (
        "exam_study_plan_settings",
        (
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("username", sa.String(length=50), nullable=False),
            sa.Column("subject_key", sa.String(length=50), nullable=False),
            sa.Column("learning_goal", sa.String(length=255), nullable=True),
            sa.Column("start_date", sa.String(length=30), nullable=True),
            sa.Column("daily_hours", sa.String(length=30), nullable=True),
            sa.Column("weekly_days", sa.Integer(), nullable=True),
            sa.Column("review_strategy", sa.String(length=30), nullable=True),
            sa.Column("show_completed", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        ),
        (
            ("idx_exam_study_plan_settings_user_subject", ["username", "subject_key"], True),
            ("ix_exam_study_plan_settings_id", ["id"], False),
            ("ix_exam_study_plan_settings_subject_key", ["subject_key"], False),
            ("ix_exam_study_plan_settings_username", ["username"], False),
        ),
    ),
    (
        "exam_study_plan_chapter_practice",
        (
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("username", sa.String(length=50), nullable=False),
            sa.Column("subject_key", sa.String(length=50), nullable=False),
            sa.Column("section_code", sa.String(length=100), nullable=False),
            sa.Column("section_title", sa.String(length=255), nullable=True),
            sa.Column("completed", sa.Boolean(), nullable=False),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        ),
        (
            ("idx_exam_study_plan_cp_user_subject_code",
             ["username", "subject_key", "section_code"], True),
            ("ix_exam_study_plan_chapter_practice_id", ["id"], False),
            ("ix_exam_study_plan_chapter_practice_section_code", ["section_code"], False),
            ("ix_exam_study_plan_chapter_practice_subject_key", ["subject_key"], False),
            ("ix_exam_study_plan_chapter_practice_username", ["username"], False),
        ),
    ),
    (
        "exam_study_plan_tasks",
        (
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("username", sa.String(length=50), nullable=False),
            sa.Column("subject_key", sa.String(length=50), nullable=False),
            sa.Column("title", sa.String(length=500), nullable=False),
            sa.Column("primary_knowledge", sa.String(length=255), nullable=True),
            sa.Column("secondary_knowledge", sa.String(length=255), nullable=True),
            sa.Column("knowledge_point_name", sa.String(length=255), nullable=True),
            sa.Column("scope_type", sa.String(length=30), nullable=False),
            sa.Column("task_type", sa.String(length=30), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("due_date", sa.String(length=30), nullable=True),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        ),
        (
            ("idx_exam_study_plan_tasks_user_subject", ["username", "subject_key"], False),
            ("ix_exam_study_plan_tasks_id", ["id"], False),
            ("ix_exam_study_plan_tasks_subject_key", ["subject_key"], False),
            ("ix_exam_study_plan_tasks_username", ["username"], False),
        ),
    ),
    (
        "ai_generated_questions",
        (
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("username", sa.String(length=50), nullable=False),
            sa.Column("subject_key", sa.String(length=50), nullable=False),
            sa.Column("subject_name", sa.String(length=50), nullable=True),
            sa.Column("knowledge_point_id", sa.String(length=100), nullable=True),
            sa.Column("knowledge_point_name", sa.String(length=255), nullable=True),
            sa.Column("knowledge_point_path", sa.Text(), nullable=True),
            sa.Column("question_type", sa.String(length=30), nullable=False),
            sa.Column("stem", sa.Text(), nullable=False),
            sa.Column("options_json", sa.Text(), nullable=True),
            sa.Column("standard_answer", sa.Text(), nullable=True),
            sa.Column("analysis", sa.Text(), nullable=True),
            sa.Column("difficulty", sa.String(length=30), nullable=True),
            sa.Column("requirement", sa.Text(), nullable=True),
            sa.Column("generation_prompt", sa.Text(), nullable=True),
            sa.Column("raw_ai_response", sa.Text(), nullable=True),
            sa.Column("generation_mode", sa.String(length=30), nullable=True),
            sa.Column("quality_status", sa.String(length=20), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        ),
        (
            ("ix_ai_generated_questions_id", ["id"], False),
            ("ix_ai_generated_questions_subject_key", ["subject_key"], False),
            ("ix_ai_generated_questions_username", ["username"], False),
        ),
    ),
    (
        "user_knowledge_progress",
        (
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=True),
            sa.Column("username", sa.String(length=50), nullable=False),
            sa.Column("course_id", sa.String(length=100), nullable=False),
            sa.Column("knowledge_point_id", sa.Integer(), nullable=False),
            sa.Column("knowledge_point_code", sa.String(length=100), nullable=True),
            sa.Column("knowledge_point_title", sa.String(length=255), nullable=True),
            sa.Column("mastery_score", sa.Integer(), nullable=True),
            sa.Column("status", sa.String(length=30), nullable=True),
            sa.Column("user_confirmed_status", sa.String(length=30), nullable=True),
            sa.Column("system_suggested_status", sa.String(length=30), nullable=True),
            sa.Column("ai_recommended_status", sa.String(length=30), nullable=True),
            sa.Column("ai_assessment", sa.Text(), nullable=True),
            sa.Column("practice_count", sa.Integer(), nullable=True),
            sa.Column("task_count", sa.Integer(), nullable=True),
            sa.Column("last_studied_at", sa.DateTime(), nullable=True),
            sa.Column("learned_at", sa.DateTime(), nullable=True),
            sa.Column("review_due_at", sa.DateTime(), nullable=True),
            sa.Column("review_interval_days", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        ),
        (
            ("ix_user_knowledge_progress_course_id", ["course_id"], False),
            ("ix_user_knowledge_progress_id", ["id"], False),
            ("ix_user_knowledge_progress_knowledge_point_code", ["knowledge_point_code"], False),
            ("ix_user_knowledge_progress_knowledge_point_id", ["knowledge_point_id"], False),
            ("ix_user_knowledge_progress_user_id", ["user_id"], False),
            ("ix_user_knowledge_progress_username", ["username"], False),
        ),
    ),
    (
        "user_knowledge_review_settings",
        (
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("username", sa.String(length=50), nullable=False),
            sa.Column("course_id", sa.String(length=100), nullable=False),
            sa.Column("review_interval_days", sa.Integer(), nullable=False, server_default="7"),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        ),
        (
            ("ix_user_knowledge_review_settings_course_id", ["course_id"], False),
            ("ix_user_knowledge_review_settings_id", ["id"], False),
            ("ix_user_knowledge_review_settings_username", ["username"], False),
        ),
    ),
)

EXAM_RUNTIME_TABLES: tuple[str, ...] = tuple(t[0] for t in TABLES)


def _existing_tables() -> set:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _existing_columns(table: str) -> set:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def _existing_indexes(table: str) -> set:
    return {i["name"] for i in sa.inspect(op.get_bind()).get_indexes(table)}


def upgrade() -> None:
    existing = _existing_tables()

    for table, columns, indexes in TABLES:
        if table not in existing:
            # --- fresh DB: create the table exactly as the models declare it
            op.create_table(table, *columns)
            for name, cols, unique in indexes:
                op.create_index(name, table, cols, unique=unique)
            continue

        # --- legacy DB: leave the table (and every row in it) alone -------------
        present_cols = _existing_columns(table)
        for column in columns:
            if not isinstance(column, sa.Column):
                continue  # PrimaryKeyConstraint — the table already has its identity
            if column.name in present_cols:
                continue
            op.add_column(table, sa.Column(
                column.name, column.type, nullable=column.nullable,
                server_default=column.server_default))

        present_idx = _existing_indexes(table)
        for name, cols, unique in indexes:
            if name not in present_idx:
                op.create_index(name, table, cols, unique=unique)


def downgrade() -> None:
    raise NotImplementedError("baseline migration; no downgrade is provided")
