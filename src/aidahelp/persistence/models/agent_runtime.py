"""阶段 7～9 的记忆、人工工单、退款申请和工具审计表。"""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from aidahelp.domain.enums import (
    RefundStatus,
    TicketStatus,
    ToolPermission,
    ToolRunStatus,
    enum_values,
)
from aidahelp.persistence.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utc_now


class ConversationMemoryModel(TimestampMixin, Base):
    """给模型使用的压缩记忆；原始聊天仍永久保存在 messages 表。"""

    __tablename__ = "conversation_memories"

    conversation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("conversations.id", ondelete="CASCADE"), primary_key=True
    )
    rolling_summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    summary_until_sequence: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    facts: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    prompt_cache_key: Mapped[str | None] = mapped_column(String(64), nullable=True)


class TicketModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """需要用户明确确认后才能创建的人工客服工单。"""

    __tablename__ = "tickets"
    __table_args__ = (Index("ix_tickets_user_status", "user_id", "status"),)

    conversation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("conversations.id", ondelete="RESTRICT"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[TicketStatus] = mapped_column(
        Enum(
            TicketStatus,
            name="ticket_status",
            native_enum=False,
            values_callable=enum_values,
            length=32,
        ),
        default=TicketStatus.OPEN,
        nullable=False,
    )


class RefundRequestModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """退款固定流程产生的写操作记录。"""

    __tablename__ = "refund_requests"
    __table_args__ = (
        Index("uq_refund_requests_idempotency_key", "idempotency_key", unique=True),
        Index("ix_refund_requests_user_status", "user_id", "status"),
    )

    conversation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("conversations.id", ondelete="RESTRICT"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    order_id: Mapped[str] = mapped_column(String(64), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[RefundStatus] = mapped_column(
        Enum(
            RefundStatus,
            name="refund_status",
            native_enum=False,
            values_callable=enum_values,
            length=32,
        ),
        default=RefundStatus.SUBMITTED,
        nullable=False,
    )


class ToolAuditModel(UUIDPrimaryKeyMixin, Base):
    """统一记录每次工具执行的来源、参数、结局和耗时。"""

    __tablename__ = "tool_audits"
    __table_args__ = (
        Index("ix_tool_audits_conversation_created", "conversation_id", "created_at"),
        Index("ix_tool_audits_tool_status", "tool_name", "status"),
    )

    conversation_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True
    )
    tool_call_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    tool_name: Mapped[str] = mapped_column(String(128), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    mcp_server: Mapped[str | None] = mapped_column(String(64), nullable=True)
    permission: Mapped[ToolPermission] = mapped_column(
        Enum(
            ToolPermission,
            name="tool_permission",
            native_enum=False,
            values_callable=enum_values,
            length=16,
        ),
        nullable=False,
    )
    arguments: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    result_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ToolRunStatus] = mapped_column(
        Enum(
            ToolRunStatus,
            name="tool_run_status",
            native_enum=False,
            values_callable=enum_values,
            length=32,
        ),
        nullable=False,
    )
    error_message: Mapped[str | None] = mapped_column(String(512), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class SecurityEventModel(UUIDPrimaryKeyMixin, Base):
    """记录鉴权失败、越权、护栏拦截等安全事件，不保存完整敏感正文。"""

    __tablename__ = "security_events"
    __table_args__ = (
        Index("ix_security_events_created", "created_at"),
        Index("ix_security_events_type_severity", "event_type", "severity"),
    )

    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    conversation_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    reason: Mapped[str] = mapped_column(String(512), nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
