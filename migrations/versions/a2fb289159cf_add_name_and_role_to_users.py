"""add name and role to users

Revision ID: a2fb289159cf
Revises: ed69656b9077
Create Date: 2026-05-19 18:56:01.075182

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a2fb289159cf'
down_revision: Union[str, Sequence[str], None] = 'ed69656b9077'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    op.add_column('users', sa.Column('name', sa.String(), nullable=True))
    op.add_column('users', sa.Column('role', sa.String(), nullable=True))

    op.add_column(
        'users',
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=True
        )
    )

    op.add_column(
        'users',
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=True
        )
    )

    op.alter_column(
        'users',
        'hashed_password',
        new_column_name='password_hash'
    )

    op.execute("UPDATE users SET name = email WHERE name IS NULL")
    op.execute("UPDATE users SET role = 'USER' WHERE role IS NULL")

    op.alter_column('users', 'name', nullable=False)
    op.alter_column('users', 'role', nullable=False)
    op.alter_column('users', 'password_hash', nullable=False)


def downgrade() -> None:
    """Downgrade schema."""

    op.alter_column(
        'users',
        'password_hash',
        new_column_name='hashed_password'
    )

    op.drop_column('users', 'updated_at')
    op.drop_column('users', 'created_at')
    op.drop_column('users', 'role')
    op.drop_column('users', 'name')
