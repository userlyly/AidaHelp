"""数据库和业务层共用的有限状态值。"""

from enum import StrEnum


def enum_values(enum_type: type[StrEnum]) -> list[str]:
    """告诉 SQLAlchemy 保存 ``active`` 这类业务值，而不是 ``ACTIVE`` 成员名。"""

    return [item.value for item in enum_type]


class UserStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"


class ConversationStatus(StrEnum):
    ACTIVE = "active"
    CLOSED = "closed"


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class MessageType(StrEnum):
    TEXT = "text"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    EVENT = "event"


class DocumentStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    DISABLED = "disabled"


class IndexStatus(StrEnum):
    """MySQL 与 Milvus 双写过程的状态，支持失败后幂等重试。"""

    PENDING = "pending"
    INDEXED = "indexed"
    FAILED = "failed"


class ToolPermission(StrEnum):
    READ = "read"
    WRITE = "write"


class ToolRunStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    VALIDATION_REJECTED = "validation_rejected"
    PERMISSION_REJECTED = "permission_rejected"


class TicketStatus(StrEnum):
    OPEN = "open"
    PROCESSING = "processing"
    CLOSED = "closed"


class RefundStatus(StrEnum):
    SUBMITTED = "submitted"
    REVIEWING = "reviewing"
    APPROVED = "approved"
    REJECTED = "rejected"
