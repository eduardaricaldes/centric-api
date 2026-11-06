"""add token_version to users

Revision ID: 7c1d2e3f4a5b
Revises: af1f491a9f89
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "7c1d2e3f4a5b"
down_revision: Union[str, Sequence[str], None] = "af1f491a9f89"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("token_version", sa.Integer(), server_default="0", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("users", "token_version")
