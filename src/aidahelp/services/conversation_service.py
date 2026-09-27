"""会话业务服务。"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from aidahelp.domain.enums import ConversationStatus, MessageRole, MessageType
from aidahelp.domain.exceptions import (
    ConversationClosedError,
    ConversationNotFoundError,
    UserNotFoundError,
)
from aidahelp.persistence.models.base import utc_now
from aidahelp.persistence.models.conversation import ConversationModel
from aidahelp.persistence.models.message import MessageModel
from aidahelp.persistence.repositories.conversation_repository import ConversationRepository
from aidahelp.persistence.repositories.message_repository import MessageRepository
from aidahelp.persistence.repositories.user_repository import UserRepository


class ConversationService:
    """负责会话业务规则，并把多次数据库操作放进同一事务。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.conversations = ConversationRepository(session)
        self.messages = MessageRepository(session)

    async def create_conversation(
        self,
        *,
        user_id: str,
        title: str | None = None,
    ) -> ConversationModel:
        async with self.session.begin():
            user = await self.users.get_by_id(user_id)
            if user is None:
                raise UserNotFoundError()

            conversation = self.conversations.add(user_id=user_id, title=title)
            # flush 会立即执行 INSERT 并生成 UUID，但事务仍由 begin 在退出时提交。
            await self.session.flush()
        return conversation

    async def get_conversation(
        self,
        *,
        conversation_id: str,
        user_id: str,
    ) -> ConversationModel:
        conversation = await self.conversations.get_for_user(
            conversation_id=conversation_id,
            user_id=user_id,
        )
        if conversation is None:
            raise ConversationNotFoundError()
        return conversation

    async def list_conversations(self, *, user_id: str, limit: int = 50) -> list[ConversationModel]:
        return await self.conversations.list_for_user(user_id=user_id, limit=limit)

    async def list_messages(
        self,
        *,
        conversation_id: str,
        user_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[MessageModel]:
        # 先校验会话归属。这样“空会话”和“无权限访问”不会被错误地当成相同结果。
        await self.get_conversation(conversation_id=conversation_id, user_id=user_id)
        return await self.messages.list_for_user(
            conversation_id=conversation_id,
            user_id=user_id,
            limit=limit,
            offset=offset,
        )

    async def append_message(
        self,
        *,
        conversation_id: str,
        user_id: str,
        role: MessageRole,
        content: str,
        message_type: MessageType = MessageType.TEXT,
        metadata: dict[str, Any] | None = None,
    ) -> MessageModel:
        """内部写消息入口，后面的 ChatService 和 Agent 都会复用它。"""

        async with self.session.begin():
            conversation = await self.conversations.lock_for_user(
                conversation_id=conversation_id,
                user_id=user_id,
            )
            if conversation is None:
                raise ConversationNotFoundError()
            if conversation.status == ConversationStatus.CLOSED:
                raise ConversationClosedError()

            sequence_no = await self.messages.next_sequence_no(conversation_id)
            message = self.messages.add(
                conversation_id=conversation_id,
                sequence_no=sequence_no,
                role=role,
                content=content,
                message_type=message_type,
                metadata=metadata,
            )
            conversation.last_message_at = utc_now()
            await self.session.flush()
        return message
