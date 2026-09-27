"""会话和消息 API 的请求、响应模型。"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from aidahelp.domain.enums import ConversationStatus, MessageRole, MessageType


class CreateConversationRequest(BaseModel):
    """创建会话时由客户端提交的数据。"""

    user_id: str | None = Field(default=None, min_length=1, max_length=36)
    title: str | None = Field(default=None, max_length=255)


class ConversationData(BaseModel):
    """向客户端展示的会话信息。"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    title: str | None
    status: ConversationStatus
    last_message_at: datetime | None
    created_at: datetime
    updated_at: datetime


class MessageData(BaseModel):
    """向客户端展示的原始消息。"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    conversation_id: str
    sequence_no: int
    role: MessageRole
    content: str
    message_type: MessageType
    # ORM 中叫 extra_data，响应 JSON 中仍使用更自然的 metadata。
    metadata: dict[str, Any] = Field(default_factory=dict, validation_alias="extra_data")
    created_at: datetime
