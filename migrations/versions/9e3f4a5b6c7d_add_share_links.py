"""add share links

Revision ID: 9e3f4a5b6c7d
Revises: 8d2e3f4a5b6c
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9e3f4a5b6c7d"
down_revision: Union[str, Sequence[str], None] = "8d2e3f4a5b6c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Links públicos de leitura; não altera dados existentes."""
    op.create_table(
        "share_links",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("token", sa.String(length=64), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "SONG",
                "EVENT",
                name="share_link_kind",
                native_enum=False,
                create_constraint=True,
                length=5,
            ),
            nullable=False,
        ),
        sa.Column("song_id", sa.Integer(), nullable=True),
        sa.Column("event_id", sa.Integer(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(kind = 'SONG' AND song_id IS NOT NULL AND event_id IS NULL)"
            " OR (kind = 'EVENT' AND event_id IS NOT NULL AND song_id IS NULL)",
            name="ck_share_links_target",
        ),
        sa.ForeignKeyConstraint(["song_id"], ["songs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["revoked_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_share_links_id"), "share_links", ["id"], unique=False)
    op.create_index(
        op.f("ix_share_links_token"), "share_links", ["token"], unique=True
    )
    op.create_index(
        op.f("ix_share_links_song_id"), "share_links", ["song_id"], unique=False
    )
    op.create_index(
        op.f("ix_share_links_event_id"), "share_links", ["event_id"], unique=False
    )


def downgrade() -> None:
    """Apaga os links: quem tiver um link recebe 404 depois disso."""
    op.drop_index(op.f("ix_share_links_event_id"), table_name="share_links")
    op.drop_index(op.f("ix_share_links_song_id"), table_name="share_links")
    op.drop_index(op.f("ix_share_links_token"), table_name="share_links")
    op.drop_index(op.f("ix_share_links_id"), table_name="share_links")
    op.drop_table("share_links")
