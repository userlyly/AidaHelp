"""阶段 3 的最小聊天闭环。"""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from aidahelp.config import Settings
from aidahelp.domain.enums import MessageRole
from aidahelp.domain.exceptions import (
    ConversationNotFoundError,
    ModelNotConfiguredError,
    ModelUnavailableError,
)
from aidahelp.integrations.llm.base import ChatMessage, ChatModel, TokenUsage
from aidahelp.integrations.llm.errors import (
    ChatModelNotConfiguredError,
    ChatModelUpstreamError,
)
from aidahelp.persistence.repositories.conversation_repository import ConversationRepository
from aidahelp.persistence.repositories.message_repository import MessageRepository
from aidahelp.services.conversation_service import ConversationService

BASIC_SYSTEM_PROMPT = """你是 AidaHelp 企业客服助手。
请使用简洁、礼貌的中文回答用户。当前阶段还没有接入企业知识库和业务工具；
如果问题需要查询订单、物流、退款进度或具体企业政策，请明确说明暂时无法核实，不能编造结果。
"""


@dataclass(frozen=True, slots=True)
class ChatTurnResult:
    """一次完整聊天回合的业务结果。"""

    conversation_id: str
    user_message_id: str
    assistant_message_id: str
    answer: str
    model: str
    usage: TokenUsage
    created_at: datetime


class ChatService:
    """协调会话、消息历史和模型调用。

    用户消息先提交数据库，再调用外部模型。这样即使模型超时，用户原始问题仍然可审计，
    同时数据库事务不会在漫长的网络请求期间一直占用连接和行锁。
    """

    def __init__(self, session: AsyncSession, model: ChatModel, settings: Settings) -> None:
        self.session = session
        self.model = model
        self.settings = settings
        self.conversation_service = ConversationService(session)
        self.conversations = ConversationRepository(session)
        self.messages = MessageRepository(session)

    async def chat(
        self,
        *,
        user_id: str,
        message: str,
        conversation_id: str | None = None,
        title: str | None = None,
    ) -> ChatTurnResult:
        if conversation_id is None:
            conversation = await self.conversation_service.create_conversation(
                user_id=user_id,
                title=title or self._default_title(message),
            )
        else:
            # 显式事务只做快速归属校验，不把事务跨越到模型网络调用阶段。
            async with self.session.begin():
                conversation = await self.conversations.get_for_user(
                    conversation_id=conversation_id,
                    user_id=user_id,
                )
                if conversation is None:
                    raise ConversationNotFoundError()

        user_message = await self.conversation_service.append_message(
            conversation_id=conversation.id,
            user_id=user_id,
            role=MessageRole.USER,
            content=message,
            metadata={"source": "chat_api"},
        )

        # 先把 ORM 对象转换成普通消息，再结束读事务，避免调用模型时长期占用数据库连接。
        async with self.session.begin():
            history = await self.messages.list_recent_for_user(
                conversation_id=conversation.id,
                user_id=user_id,
                limit=self.settings.llm_history_limit,
            )
            model_messages = [ChatMessage(role="system", content=BASIC_SYSTEM_PROMPT)]
            model_messages.extend(
                ChatMessage(role=item.role.value, content=item.content)
                for item in history
                if item.role in {MessageRole.USER, MessageRole.ASSISTANT, MessageRole.SYSTEM}
            )

        try:
            model_response = await self.model.generate(model_messages)
        except ChatModelNotConfiguredError as exc:
            raise ModelNotConfiguredError() from exc
        except ChatModelUpstreamError as exc:
            raise ModelUnavailableError() from exc

        usage_metadata = {
            "prompt_tokens": model_response.usage.prompt_tokens,
            "completion_tokens": model_response.usage.completion_tokens,
            "total_tokens": model_response.usage.total_tokens,
        }
        assistant_message = await self.conversation_service.append_message(
            conversation_id=conversation.id,
            user_id=user_id,
            role=MessageRole.ASSISTANT,
            content=model_response.content,
            metadata={
                "model": model_response.model,
                "provider_request_id": model_response.provider_request_id,
                "usage": usage_metadata,
                **model_response.raw_metadata,
            },
        )
        return ChatTurnResult(
            conversation_id=conversation.id,
            user_message_id=user_message.id,
            assistant_message_id=assistant_message.id,
            answer=assistant_message.content,
            model=model_response.model,
            usage=model_response.usage,
            created_at=assistant_message.created_at,
        )

    @staticmethod
    def _default_title(message: str) -> str:
        """阶段 3 使用确定性标题，避免为了标题再额外消耗一次模型调用。"""

        compact = " ".join(message.split())
        return compact[:30] or "新客服会话"
