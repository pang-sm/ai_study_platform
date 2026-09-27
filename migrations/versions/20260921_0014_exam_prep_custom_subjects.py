"""exam_prep_profiles: a learner's own subjects (自命题专业课)

A custom subject belongs to a person, not to the taxonomy. The national catalogue
(``exam_prep.catalog``) is frozen config, so adding 自命题专业课 to it would claim a fifteenth
national subject exists with no content behind it — and a learner's own subject name would be
visible to nobody in particular and owned by everybody.

Additive only: one nullable-free JSON column defaulted to an empty list, so every existing
profile reads as "no custom subjects" without a backfill. No index is added because the column is
never queried — it is read and written whole, with the profile row.

Revision ID: 20260921_0014
Revises: 20260921_0013
"""

from typing import Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260921_0014"
down_revision: Union[str, None] = "20260921_0013"
branch_labels = None
depends_on = None

def _has_column(table: str) -> bool:
    bind = op.get_bind()
    rows = bind.exec_driver_sql(f"PRAGMA table_info({table})").fetchall()
    return any(row[1] == "custom_subjects_json" for row in rows)

def _has_table(table: str) -> bool:
    bind = op.get_bind()
    row = bind.exec_driver_sql(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return row is not None

def upgrade() -> None:
    # `exam_prep_profiles` is created by revision 20260917_0007, but a legacy-managed database can
    # reach this revision without it. Same guard the surrounding revisions use: add the column
    # only where the table exists and does not already carry it.
    if not _has_table("exam_prep_profiles") or _has_column("exam_prep_profiles"):
        return
    op.add_column(
        "exam_prep_profiles",
        sa.Column("custom_subjects_json", sa.Text(), nullable=False, server_default="[]"),
    )

def downgrade() -> None:
    # Additive-only project rule: no destructive downgrade is provided.
    pass
