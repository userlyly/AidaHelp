"""Add security event audit table.

Revision ID: 0004_security_events
Revises: 0003_agent_runtime
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_security_events"
down_revision: str | None = "0003_agent_runtime"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "security_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("user_id", sa.String(36), nullable=True),
        sa.Column("conversation_id", sa.String(36), nullable=True),
        sa.Column("trace_id", sa.String(128), nullable=True),
        sa.Column("reason", sa.String(512), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_security_events_created", "security_events", ["created_at"])
    op.create_index(
        "ix_security_events_type_severity",
        "security_events",
        ["event_type", "severity"],
    )


def downgrade() -> None:
    op.drop_table("security_events")
