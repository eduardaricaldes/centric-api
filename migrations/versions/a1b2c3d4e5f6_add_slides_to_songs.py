"""add slides to songs

Slides da projeção ajustados à mão (Fase 2). Vazio = slides automáticos,
uma estrofe por slide.

Revision ID: a1b2c3d4e5f6
Revises: 9e3f4a5b6c7d
Create Date: 2026-11-24 23:50:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "9e3f4a5b6c7d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("songs", sa.Column("slides", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("songs", "slides")
