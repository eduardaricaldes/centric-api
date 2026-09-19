"""set playlist title length 255

Revision ID: 6902f251c9e5
Revises: 96a3a243dc12
Create Date: 2026-09-19 12:05:17.877207

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6902f251c9e5'
down_revision: Union[str, Sequence[str], None] = '96a3a243dc12'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column('playlists', 'title',
               existing_type=sa.String(),
               type_=sa.String(255),
               existing_nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column('playlists', 'title',
               existing_type=sa.String(255),
               type_=sa.String(),
               existing_nullable=False)
