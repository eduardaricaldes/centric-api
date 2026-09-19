"""add events assignments and preaching

Revision ID: a4f2c8d91e63
Revises: fbba793089e2
Create Date: 2026-09-19 15:20:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a4f2c8d91e63"
down_revision: Union[str, Sequence[str], None] = "fbba793089e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the phase 4 tables without changing existing playlist rows."""
    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("time", sa.Time(), nullable=False),
        sa.Column(
            "type",
            sa.Enum(
                "CULTO_DOMINGO",
                "ENSAIO",
                "EVENTO",
                name="event_type",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "RASCUNHO",
                "PUBLICADO",
                name="event_status",
                native_enum=False,
                create_constraint=True,
            ),
            server_default="RASCUNHO",
            nullable=False,
        ),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_events_id"), "events", ["id"], unique=False)
    op.create_index(op.f("ix_events_date"), "events", ["date"], unique=False)
    op.create_index(
        op.f("ix_events_created_by"), "events", ["created_by"], unique=False
    )

    op.create_table(
        "assignments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("ministry_id", sa.Integer(), nullable=False),
        sa.Column("function", sa.String(length=100), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "CONVIDADO",
                "CONFIRMADO",
                "RECUSADO",
                name="assignment_status",
                native_enum=False,
                create_constraint=True,
            ),
            server_default="CONVIDADO",
            nullable=False,
        ),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ministry_id"], ["ministries.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_assignments_id"), "assignments", ["id"], unique=False
    )
    op.create_index(
        op.f("ix_assignments_event_id"),
        "assignments",
        ["event_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_assignments_user_id"),
        "assignments",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_assignments_ministry_id"),
        "assignments",
        ["ministry_id"],
        unique=False,
    )

    op.create_table(
        "preachings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("preacher_id", sa.Integer(), nullable=False),
        sa.Column("theme", sa.String(length=255), nullable=False),
        sa.Column("bible_reference", sa.String(length=255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["preacher_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_preachings_id"), "preachings", ["id"], unique=False
    )
    op.create_index(
        op.f("ix_preachings_event_id"),
        "preachings",
        ["event_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_preachings_preacher_id"),
        "preachings",
        ["preacher_id"],
        unique=False,
    )

    op.add_column("playlists", sa.Column("event_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_playlists_event_id_events",
        "playlists",
        "events",
        ["event_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        op.f("ix_playlists_event_id"),
        "playlists",
        ["event_id"],
        unique=True,
    )


def downgrade() -> None:
    """Remove phase 4 while preserving the pre-existing playlist data."""
    op.drop_index(op.f("ix_playlists_event_id"), table_name="playlists")
    op.drop_constraint(
        "fk_playlists_event_id_events",
        "playlists",
        type_="foreignkey",
    )
    op.drop_column("playlists", "event_id")

    op.drop_index(op.f("ix_preachings_preacher_id"), table_name="preachings")
    op.drop_index(op.f("ix_preachings_event_id"), table_name="preachings")
    op.drop_index(op.f("ix_preachings_id"), table_name="preachings")
    op.drop_table("preachings")

    op.drop_index(op.f("ix_assignments_ministry_id"), table_name="assignments")
    op.drop_index(op.f("ix_assignments_user_id"), table_name="assignments")
    op.drop_index(op.f("ix_assignments_event_id"), table_name="assignments")
    op.drop_index(op.f("ix_assignments_id"), table_name="assignments")
    op.drop_table("assignments")

    op.drop_index(op.f("ix_events_created_by"), table_name="events")
    op.drop_index(op.f("ix_events_date"), table_name="events")
    op.drop_index(op.f("ix_events_id"), table_name="events")
    op.drop_table("events")
