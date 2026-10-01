"""practice questions carry the ability they test, so the next set can avoid repeating it

Revision ID: 20261001_0018
Revises: 20260930_0017

WHY THIS REVISION EXISTS
------------------------
A learner asked 专业学习 → 练习 for ten questions on 「循环队列」 and got ten near-identical
restatements of the point's title. The questions were structurally valid, so nothing refused
them: the schema could tell a question apart from a paragraph, but not a question about the
knowledge apart from a question about the syllabus.

Two of the three fields added here are what make that distinction enforceable on the NEXT set
rather than only within the set being built:

    assessment_target      the specific ability the question exercises ("队列长度计算"),
                           not the point it belongs to
    cognitive_level        understand / apply / analyze / evaluate / synthesize
    question_fingerprint   a stable id for the question's WORDING, so the same question
                           rephrased is still recognisable as a repeat

Without them, "don't ask me that again" can only reach back to the exact stems of the last 60
rows. With them, a new set can decline to re-ask an ability the learner has just been asked
about, and a batch's ability coverage can be MEASURED after the fact instead of being asserted
while it is built.

All three are nullable and additive: the rows already in the table keep answering exactly as
they did, and nothing reads them except the practice generator.

The fields are SERVER-SIDE ONLY. No endpoint sends any of them to a learner — they are not on
``CoursePracticeQuestionView`` and must never be added to it.

Note on REASONING and the token budget this revision's caller changed: the shipped
``max_tokens`` per set was sized for the visible answer alone, and the pool's cheapest
qualified model bills hidden reasoning inside that same budget. The 10-question request above
returned ``finish_reason=length`` with 5,552 of 6,000 tokens spent reasoning, so the JSON
ended mid-object. That is a code change (``practice.py``), not a schema change — recorded here
because the two shipped together and the migration alone does not explain the incident.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from migrations.guards import add_column_if_absent, create_index_if_absent

revision: str = "20261001_0018"
down_revision: Union[str, None] = "20260930_0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    add_column_if_absent("ai_generated_questions", sa.Column("assessment_target", sa.String(255), nullable=True))
    add_column_if_absent("ai_generated_questions", sa.Column("cognitive_level", sa.String(30), nullable=True))
    add_column_if_absent("ai_generated_questions", sa.Column("question_fingerprint", sa.String(64), nullable=True))
    create_index_if_absent("ix_ai_generated_questions_question_fingerprint",
                           "ai_generated_questions", ["question_fingerprint"])


def downgrade():
    # Forward-only, like the chain it extends. Dropping these columns would erase the record of
    # which abilities a learner has already been asked about, and the avoidance that reads them
    # would then silently start repeating questions. Additive columns cost nothing to keep.
    pass
