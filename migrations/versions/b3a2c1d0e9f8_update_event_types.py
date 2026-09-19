"""update event types

Revision ID: b3a2c1d0e9f8
Revises: c5d8e12f4a76
Create Date: 2026-09-19 14:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b3a2c1d0e9f8"
down_revision: Union[str, Sequence[str], None] = "c5d8e12f4a76"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("event_type", "events", type_="check")
    op.alter_column(
        "events",
        "type",
        type_=sa.String(length=16),
        existing_nullable=False,
    )
    op.execute("UPDATE events SET type = 'CULTO' WHERE type = 'CULTO_DOMINGO'")
    op.execute("UPDATE events SET type = 'EVENTO_ESPECIAL' WHERE type = 'EVENTO'")
    op.create_check_constraint(
        "event_type",
        "events",
        "type IN ('CULTO','ENSAIO','CONFRATERNIZACAO','ACAO_MISSIONARIA','EVENTO_ESPECIAL','OUTRO')",
    )


def downgrade() -> None:
    op.drop_constraint("event_type", "events", type_="check")
    op.execute("UPDATE events SET type = 'CULTO_DOMINGO' WHERE type = 'CULTO'")
    op.execute(
        "UPDATE events SET type = 'EVENTO'"
        " WHERE type IN ('CONFRATERNIZACAO','ACAO_MISSIONARIA','EVENTO_ESPECIAL','OUTRO')"
    )
    op.alter_column(
        "events",
        "type",
        type_=sa.String(length=13),
        existing_nullable=False,
    )
    op.create_check_constraint(
        "event_type",
        "events",
        "type IN ('CULTO_DOMINGO','ENSAIO','EVENTO')",
    )
