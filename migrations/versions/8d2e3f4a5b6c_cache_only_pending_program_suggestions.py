"""cache only pending program suggestions

Revision ID: 8d2e3f4a5b6c
Revises: 7c1d2e3f4a5b
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "8d2e3f4a5b6c"
down_revision: Union[str, Sequence[str], None] = "7c1d2e3f4a5b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index(
        op.f("ix_program_suggestions_request_hash"),
        table_name="program_suggestions",
    )
    op.create_index(
        op.f("ix_program_suggestions_request_hash"),
        "program_suggestions",
        ["request_hash"],
        unique=False,
    )
    op.create_index(
        "uq_program_suggestions_pending_request_hash",
        "program_suggestions",
        ["request_hash"],
        unique=True,
        postgresql_where=sa.text("applied_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_program_suggestions_pending_request_hash",
        table_name="program_suggestions",
    )
    op.drop_index(
        op.f("ix_program_suggestions_request_hash"),
        table_name="program_suggestions",
    )
    op.create_index(
        op.f("ix_program_suggestions_request_hash"),
        "program_suggestions",
        ["request_hash"],
        unique=True,
    )
