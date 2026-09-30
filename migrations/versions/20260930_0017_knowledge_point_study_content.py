"""stored knowledge-point explanations, so a point is not paid for twice

Revision ID: 20260930_0017
Revises: 20260923_0016

WHY THIS REVISION EXISTS
------------------------
学习 becomes a workspace around ONE knowledge point: the learner opens a point and reads an
explanation of it, grounded in their own materials. That explanation is an AI call, which
costs real credits and takes tens of seconds, and its subject does not change between two
visits.

Without a row to put it in, every reload — or every step to another point and back — would
buy the same explanation again. That is the one behaviour that makes a learning page
untrustworthy, and it is what this table removes: one stored explanation per point, read for
free, regenerated only when the learner asks for a new one.

The table holds CONTENT, never a learning fact. Reading an explanation moves no status and
writes no progress; the four-state progress a learner sets by hand lives in
``user_knowledge_progress`` and is untouched here.

``username`` and ``knowledge_point_id`` are both stored because the point id alone is not the
scope: a point belongs to exactly one learner's structure version, and the pair is what the
unique index enforces. ``structure_id`` is provenance — it says which version the point was
in when the explanation was written — and ``citations_json`` records which of the learner's
files actually grounded the answer, so the page can show a citation that is checkable rather
than one assembled from a link that exists for other reasons.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from migrations.guards import create_index_if_absent, create_table_if_absent

revision: str = "20260930_0017"
down_revision: Union[str, None] = "20260923_0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    create_table_if_absent(
        "knowledge_point_study_content",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(50), nullable=False),
        sa.Column("course_id", sa.String(100), nullable=False),
        sa.Column("knowledge_point_id", sa.Integer(), nullable=False),
        sa.Column("structure_id", sa.Integer(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("citations_json", sa.Text(), nullable=True),
        sa.Column("grounding_mode", sa.String(30), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    create_index_if_absent("ix_knowledge_point_study_content_username",
                           "knowledge_point_study_content", ["username"])
    create_index_if_absent("ix_knowledge_point_study_content_course_id",
                           "knowledge_point_study_content", ["course_id"])
    create_index_if_absent("ix_knowledge_point_study_content_knowledge_point_id",
                           "knowledge_point_study_content", ["knowledge_point_id"])
    # ONE explanation per point: a regenerate replaces the row rather than appending. A page
    # that had to choose between several stored answers would be asking the learner to make a
    # decision the product has no basis to make on their behalf.
    create_index_if_absent("idx_kp_study_content_point",
                           "knowledge_point_study_content",
                           ["username", "knowledge_point_id"], unique=True)


def downgrade():
    # Forward-only, like the chain it extends. Dropping this table would discard explanations
    # the learner already spent credits on, and nothing about the rest of the schema depends
    # on it being gone.
    pass
