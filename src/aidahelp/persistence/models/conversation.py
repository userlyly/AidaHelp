"""客服会话 ORM 模型。"""

from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from aidahelp.domain.enums import ConversationStatus, enum_values
from aidahelp.persistence.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ConversationModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """一次独立客服会话；后续 LangGraph 会把它的 ID 作为 thread_id。"""

    __tablename__ = "conversations"
    __table_args__ = (
        Index("ix_conversations_user_created", "user_id", "created_at"),
        Index("ix_conversations_user_status", "user_id", "status"),
    )

    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[ConversationStatus] = mapped_column(
        Enum(
            ConversationStatus,
            name="conversation_status",
            native_enum=False,
            create_constraint=True,
            values_callable=enum_values,
            length=32,
        ),
        default=ConversationStatus.ACTIVE,
        server_default=ConversationStatus.ACTIVE.value,
        nullable=False,
    )
    last_message_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        index=True,
        nullable=True,
    )
