"""原始聊天消息 ORM 模型。"""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from aidahelp.domain.enums import MessageRole, MessageType, enum_values
from aidahelp.persistence.models.base import Base, UUIDPrimaryKeyMixin, utc_now


class MessageModel(UUIDPrimaryKeyMixin, Base):
    """永久保存的一条原始消息。

    后续即使把旧聊天压缩成摘要，这里的原文仍然保留，用于审计、排障和重新评测。
    """

    __tablename__ = "messages"
    __table_args__ = (
        # sequence_no 保证消息在同一会话中有稳定顺序，同时防止同一序号重复写入。
        Index(
            "uq_messages_conversation_sequence",
            "conversation_id",
            "sequence_no",
            unique=True,
        ),
        Index("ix_messages_conversation_created", "conversation_id", "created_at"),
    )

    conversation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[MessageRole] = mapped_column(
        Enum(
            MessageRole,
            name="message_role",
            native_enum=False,
            create_constraint=True,
            values_callable=enum_values,
            length=32,
        ),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    message_type: Mapped[MessageType] = mapped_column(
        Enum(
            MessageType,
            name="message_type",
            native_enum=False,
            create_constraint=True,
            values_callable=enum_values,
            length=32,
        ),
        default=MessageType.TEXT,
        server_default=MessageType.TEXT.value,
        nullable=False,
    )
    # metadata 是 SQLAlchemy 的保留属性，因此 Python 中命名 extra_data，数据库列仍叫 metadata。
    extra_data: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSON,
        default=dict,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
