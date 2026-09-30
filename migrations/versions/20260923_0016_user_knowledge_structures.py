"""user-level versioned knowledge structures

Revision ID: 20260923_0016
Revises: 20260923_0015

WHY THIS REVISION EXISTS
------------------------
The knowledge structure a learner studies from is USER + COURSE scoped data: two learners
taking 数据结构 may each build their own tree from their own materials, and neither
generation may touch the other's points or progress. ``knowledge_points`` already carries
``username``, so that boundary existed — what did not exist was a VERSION for it.

Before this revision, generating a structure REPLACED the previous one in place: the old
points (and their ``user_knowledge_progress`` rows, wrong-answer links and review schedule)
were deleted with them, and the new tree started from zero. That is the destructive path
this revision makes impossible: a generate now writes a draft version, the version in use
stays active until the draft is confirmed, and the replaced version is marked superseded
rather than deleted — so the progress rows that reference its points survive the switch.

The two ``knowledge_points`` columns are what attach a point to its version and record
whether the point's title came from the learner's own files or was supplied by the model.
They are nullable on purpose: every point written before this revision has no version, and
a NULL ``structure_id`` is read as the legacy active structure for its course.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from migrations.guards import (
    add_column_if_absent,
    create_index_if_absent,
    create_table_if_absent,
)

revision: str = "20260923_0016"
down_revision: Union[str, None] = "20260923_0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    create_table_if_absent(
        "user_knowledge_structures",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("username", sa.String(50), nullable=False),
        sa.Column("course_id", sa.String(100), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("source_mode", sa.String(30), nullable=False, server_default="ai_generated"),
        sa.Column("source_file_ids", sa.Text(), nullable=True),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("goal", sa.String(120), nullable=True),
        sa.Column("point_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("chapter_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(), nullable=True),
        sa.Column("superseded_at", sa.DateTime(), nullable=True),
        # AUTOINCREMENT, not a bare PRIMARY KEY: SQLite otherwise reuses the rowid of a
        # deleted row, and discarding a draft would hand the next draft the version id the
        # discarded one released — making knowledge_points.structure_id ambiguous.
        sqlite_autoincrement=True,
    )
    create_index_if_absent("ix_user_knowledge_structures_username",
                           "user_knowledge_structures", ["username"])
    create_index_if_absent("ix_user_knowledge_structures_course_id",
                           "user_knowledge_structures", ["course_id"])
    create_index_if_absent("ix_user_knowledge_structures_status",
                           "user_knowledge_structures", ["status"])
    create_index_if_absent("idx_user_knowledge_structures_scope",
                           "user_knowledge_structures", ["username", "course_id", "status"])

    # `knowledge_points` is a LEGACY table: the application creates it at startup, this chain
    # never did. A fresh alembic-only database therefore has no such table — and that is
    # legitimate, because the ORM model already declares both new columns, so they arrive
    # WITH the table. Demanding the table here would abort a fresh install for no reason.
    existing_tables = set(sa.inspect(op.get_bind()).get_table_names())
    if "knowledge_points" in existing_tables:
        add_column_if_absent("knowledge_points", sa.Column("structure_id", sa.Integer(), nullable=True))
        add_column_if_absent("knowledge_points", sa.Column("origin", sa.String(30), nullable=True))
        op.execute("UPDATE knowledge_points SET origin = 'source_extracted' WHERE origin IS NULL")
    else:
        print("[20260923_0016] knowledge_points does not exist yet (legacy-managed table); the "
              "ORM model creates structure_id and origin with it at startup — nothing to alter.")
        return

    create_index_if_absent("idx_knowledge_points_structure_id", "knowledge_points", ["structure_id"])

    # ADOPT the points that already exist. Each (username, course_id) that holds points is a
    # learner who already has a structure — they simply had no version record for it. Writing
    # one ACTIVE version per such pair keeps every pre-existing point and its progress row
    # exactly where it is; nothing is deleted, moved or rewritten.
    #
    # `source_mode` is 'selected_materials' for these because the only way a point could have
    # been created before this revision was material-based generation. That is a statement
    # about how the row came to exist, not a guess about its content.
    bind = op.get_bind()
    bind.execute(sa.text("""
        INSERT INTO user_knowledge_structures
            (user_id, username, course_id, version, status, source_mode, source_file_ids,
             title, point_count, chapter_count, created_at, confirmed_at)
        SELECT
            u.id, kp.username, kp.course_id, 1, 'active', 'selected_materials', NULL,
            kp.course_id, 0, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
        FROM (SELECT DISTINCT username, course_id FROM knowledge_points) kp
        LEFT JOIN users u ON u.username = kp.username
    """))

    # Attach each pre-existing point to the version just created for its own (user, course).
    bind.execute(sa.text("""
        UPDATE knowledge_points
        SET structure_id = (
            SELECT s.id FROM user_knowledge_structures s
            WHERE s.username = knowledge_points.username
              AND s.course_id = knowledge_points.course_id
              AND s.status = 'active'
            ORDER BY s.id ASC LIMIT 1
        )
        WHERE structure_id IS NULL
    """))

    # The counts are DERIVED from the points that were just attached, so the stored metadata
    # agrees with the rows it describes instead of being a second, drifting source of truth.
    bind.execute(sa.text("""
        UPDATE user_knowledge_structures
        SET point_count = (
                SELECT COUNT(*) FROM knowledge_points kp
                WHERE kp.structure_id = user_knowledge_structures.id AND kp.parent_id IS NOT NULL
            ),
            chapter_count = (
                SELECT COUNT(*) FROM knowledge_points kp
                WHERE kp.structure_id = user_knowledge_structures.id AND kp.parent_id IS NULL
            )
    """))


def downgrade():
    # Forward-only. Dropping the version table would orphan every point's structure_id, and
    # restoring the pre-revision "no versions at all" state would mean deleting the
    # superseded versions this revision exists to preserve.
    pass
