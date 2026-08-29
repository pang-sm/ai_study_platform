"""Shared additive SQLite schema initialization for the programming catalog.

The catalog scripts and the API must use this one migration entry point.  It
only adds missing columns and never drops, rebuilds, or rewrites existing
tables or rows.
"""

from __future__ import annotations

from collections.abc import Mapping

from sqlalchemy import Engine, create_engine


PROGRAMMING_EXERCISE_COLUMNS: Mapping[str, str] = {
    "is_active": "BOOLEAN NOT NULL DEFAULT 1",
    "problem_family_id": "VARCHAR(160)",
    "language_fit_reason": "TEXT",
    "title_zh": "VARCHAR(255)",
    "summary_zh": "TEXT",
    "statement_zh": "TEXT",
    "input_format_zh": "TEXT",
    "output_format_zh": "TEXT",
    "constraints_zh": "TEXT",
    "title_en": "VARCHAR(255)",
    "statement_en": "TEXT",
    "quality_status": "VARCHAR(20) NOT NULL DEFAULT 'needs_review'",
    "quality_score": "FLOAT NOT NULL DEFAULT 0",
    "quality_failure_reasons": "TEXT NOT NULL DEFAULT '[]'",
    "learning_objective_id": "VARCHAR(160)",
    "learning_objective": "TEXT",
    "prerequisites": "TEXT",
    "core_skill": "TEXT",
    "novelty_reason": "TEXT",
    "reviewed_at": "TEXT",
    "background_knowledge_zh": "TEXT",
    "hints_zh": "TEXT",
    "knowledge_point_ids": "TEXT NOT NULL DEFAULT '[]'",
    "primary_knowledge_point_id": "INTEGER",
    "prerequisite_knowledge_point_ids": "TEXT NOT NULL DEFAULT '[]'",
    "curriculum_module": "VARCHAR(120)",
    "level": "VARCHAR(20)",
    "difficulty_score": "FLOAT",
    "estimated_minutes": "INTEGER",
}


REDEMPTION_CODE_COLUMNS: Mapping[str, str] = {
    "service_key": "VARCHAR(50)",
    "target_plan": "VARCHAR(50)",
    "membership_duration_days": "INTEGER",
    "code_expires_at": "DATETIME",
    "note": "TEXT",
}

# AI usage service isolation (nullable → legacy rows keep NULL, never backfilled).
AI_USAGE_LOG_COLUMNS: Mapping[str, str] = {
    "service_key": "VARCHAR(50)",
}


def ensure_programming_exercise_schema(engine: Engine) -> dict:
    """Add missing catalog columns and return an auditable migration result."""

    with engine.begin() as connection:
        existing = {
            row[1]
            for row in connection.exec_driver_sql(
                "PRAGMA table_info(programming_exercises)"
            ).fetchall()
        }
        if not existing:
            raise RuntimeError(
                "programming_exercises table does not exist; initialize ORM tables first"
            )

        added: list[str] = []
        for name, definition in PROGRAMMING_EXERCISE_COLUMNS.items():
            if name not in existing:
                connection.exec_driver_sql(
                    f"ALTER TABLE programming_exercises ADD COLUMN {name} {definition}"
                )
                added.append(name)
        final = {
            row[1]
            for row in connection.exec_driver_sql(
                "PRAGMA table_info(programming_exercises)"
            ).fetchall()
        }
    return {"table": "programming_exercises", "added": added, "columns": sorted(final)}


def ensure_database_schema(engine_or_url: Engine | str) -> dict:
    """Canonical migration entry point used by the API and every catalog script."""

    engine = (
        create_engine(engine_or_url, connect_args={"check_same_thread": False})
        if isinstance(engine_or_url, str)
        else engine_or_url
    )
    result = ensure_programming_exercise_schema(engine)
    with engine.begin() as connection:
        existing = {
            row[1]
            for row in connection.exec_driver_sql(
                "PRAGMA table_info(redemption_codes)"
            ).fetchall()
        }
        added: list[str] = []
        for name, definition in REDEMPTION_CODE_COLUMNS.items():
            if name not in existing:
                connection.exec_driver_sql(
                    f"ALTER TABLE redemption_codes ADD COLUMN {name} {definition}"
                )
                added.append(name)
    result["redemption_codes"] = {"added": added}

    with engine.begin() as connection:
        existing = {
            row[1]
            for row in connection.exec_driver_sql(
                "PRAGMA table_info(ai_usage_logs)"
            ).fetchall()
        }
        added: list[str] = []
        for name, definition in AI_USAGE_LOG_COLUMNS.items():
            if name not in existing:
                connection.exec_driver_sql(
                    f"ALTER TABLE ai_usage_logs ADD COLUMN {name} {definition}"
                )
                added.append(name)
    result["ai_usage_logs"] = {"added": added}
    return result
