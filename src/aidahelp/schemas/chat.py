"""聊天接口的数据结构。"""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class ChatRequest(BaseModel):
    """用户发起一个聊天回合。conversation_id 为空时自动创建新会话。"""

    user_id: str | None = Field(default=None, min_length=1, max_length=36)
    conversation_id: str | None = Field(default=None, min_length=1, max_length=36)
    message: str = Field(min_length=1, max_length=8000)
    title: str | None = Field(default=None, max_length=255)

    @field_validator("message")
    @classmethod
    def message_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("message 不能只包含空白字符")
        return value


class TokenUsageData(BaseModel):
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


class ChatResponseData(BaseModel):
    conversation_id: str
    user_message_id: str | None = None
    assistant_message_id: str
    answer: str
    model: str
    usage: TokenUsageData
    created_at: datetime
    intent: str | None = None
    route: str | None = None
    citations: list[dict] = Field(default_factory=list)
    pending_action: dict | None = None


class ResumeRequest(BaseModel):
    """恢复被 interrupt 暂停的写操作；用户身份仍需参与归属校验。"""

    user_id: str | None = Field(default=None, min_length=1, max_length=36)
    confirmed: bool
