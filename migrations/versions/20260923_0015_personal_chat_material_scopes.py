"""personal/chat material scopes and multi-message attachments

Revision ID: 20260923_0015
Revises: 20260921_0014
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from migrations.guards import (
    add_column_if_absent,
    create_index_if_absent,
    create_table_if_absent,
)

# Annotated like the rest of the chain: the chain-integrity tests read the revision graph by
# parsing these declarations, and a bare assignment is invisible to that reader — this revision
# would be silently missing from the graph rather than counted as its head.
revision: str = "20260923_0015"
down_revision: Union[str, None] = "20260921_0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # `study_materials` / `material_chunks` are LEGACY tables: this chain does not create them,
    # the application does (`Base.metadata.create_all` / `ensure_database_schema` at startup).
    # A fresh, alembic-only database therefore has neither, and that is legitimate — the ORM
    # model already declares `scope_type` (NOT NULL, default 'course', indexed) and a nullable
    # `subject`, so both facts this revision exists to establish arrive WITH the table.
    #
    # Demanding the table here aborts a fresh install for no reason; altering it unguarded
    # aborts any database that has no such table. Same rule 20260921_0013 applies to `users`.
    existing_tables = set(sa.inspect(op.get_bind()).get_table_names())

    if "study_materials" in existing_tables:
        add_column_if_absent(
            "study_materials",
            sa.Column("scope_type", sa.String(20), nullable=False, server_default="course"))
        op.execute("UPDATE study_materials SET scope_type = 'course' "
                   "WHERE scope_type IS NULL OR scope_type = ''")
        create_index_if_absent("ix_study_materials_scope_type", "study_materials", ["scope_type"])
        with op.batch_alter_table("study_materials") as batch:
            batch.alter_column("subject", existing_type=sa.String(100), nullable=True)
    else:
        print("[20260923_0015] study_materials does not exist yet (legacy-managed table); the "
              "ORM model creates scope_type (NOT NULL, default 'course') and a nullable subject "
              "with it at startup — nothing to alter here.")

    if "material_chunks" in existing_tables:
        with op.batch_alter_table("material_chunks") as batch:
            batch.alter_column("subject", existing_type=sa.String(100), nullable=True)
    else:
        print("[20260923_0015] material_chunks does not exist yet (legacy-managed table); the "
              "ORM model creates a nullable subject with it at startup — nothing to alter here.")

    # This table IS owned by this revision, so it is created here rather than skipped. Guarded
    # like the rest of the chain because the same model is reachable through `create_all`: a
    # database that already has it (from an app start on current models) must adopt it, not
    # abort the deployment on "table already exists".
    create_table_if_absent(
        "chat_message_attachments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("message_id", sa.Integer(), sa.ForeignKey("chat_messages.id"), nullable=False),
        sa.Column("material_id", sa.Integer(), sa.ForeignKey("study_materials.id"), nullable=False),
        sa.Column("source_kind", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("message_id", "material_id", name="uq_chat_message_attachment_material"),
    )
    create_index_if_absent("ix_chat_message_attachments_message_id",
                           "chat_message_attachments", ["message_id"])
    create_index_if_absent("ix_chat_message_attachments_material_id",
                           "chat_message_attachments", ["material_id"])


def downgrade():
    op.drop_table("chat_message_attachments")
    # SQLite cannot safely restore NOT NULL where Personal/Chat rows use NULL; forward-only.
