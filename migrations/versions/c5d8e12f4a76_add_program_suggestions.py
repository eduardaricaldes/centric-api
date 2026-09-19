"""add program suggestions

Revision ID: c5d8e12f4a76
Revises: a4f2c8d91e63
Create Date: 2026-09-19 17:20:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c5d8e12f4a76"
down_revision: Union[str, Sequence[str], None] = "a4f2c8d91e63"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add persistent AI drafts without changing existing event data."""
    op.create_table(
        "program_suggestions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("briefing", sa.Text(), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("response", sa.JSON(), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("provider_model", sa.String(length=100), nullable=False),
        sa.Column("requested_by", sa.Integer(), nullable=False),
        sa.Column("applied_response", sa.JSON(), nullable=True),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("applied_by", sa.Integer(), nullable=True),
        sa.Column("playlist_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["applied_by"], ["users.id"]),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["events.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["playlist_id"],
            ["playlists.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(["requested_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_program_suggestions_id"),
        "program_suggestions",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_program_suggestions_event_id"),
        "program_suggestions",
        ["event_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_program_suggestions_requested_by"),
        "program_suggestions",
        ["requested_by"],
        unique=False,
    )
    op.create_index(
        op.f("ix_program_suggestions_request_hash"),
        "program_suggestions",
        ["request_hash"],
        unique=True,
    )


def downgrade() -> None:
    """Remove stored program drafts; event and playlist data remain untouched."""
    op.drop_index(
        op.f("ix_program_suggestions_request_hash"),
        table_name="program_suggestions",
    )
    op.drop_index(
        op.f("ix_program_suggestions_requested_by"),
        table_name="program_suggestions",
    )
    op.drop_index(
        op.f("ix_program_suggestions_event_id"),
        table_name="program_suggestions",
    )
    op.drop_index(
        op.f("ix_program_suggestions_id"),
        table_name="program_suggestions",
    )
    op.drop_table("program_suggestions")
