"""rename is_musician to prefers_chords

Revision ID: d4e5f6a7b8c9
Revises: b3a2c1d0e9f8
Create Date: 2026-09-19 14:10:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "b3a2c1d0e9f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("users", "is_musician", new_column_name="prefers_chords")


def downgrade() -> None:
    op.alter_column("users", "prefers_chords", new_column_name="is_musician")
