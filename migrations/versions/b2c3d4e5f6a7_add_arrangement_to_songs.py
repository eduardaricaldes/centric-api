"""add arrangement to songs

Versões da música: cada versão é uma música com o mesmo título e artista, tom
e arranjo próprios. O arranjo é texto livre (dinâmica, quem entra quando).

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-11-25 00:10:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("songs", sa.Column("arrangement", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("songs", "arrangement")
