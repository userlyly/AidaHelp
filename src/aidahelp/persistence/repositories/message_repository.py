"""消息数据访问。"""

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from aidahelp.domain.enums import MessageRole, MessageType
from aidahelp.persistence.models.conversation import ConversationModel
from aidahelp.persistence.models.message import MessageModel


class MessageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def next_sequence_no(self, conversation_id: str) -> int:
        """计算下一条消息序号；调用前必须先锁定所属会话。"""

        statement = select(func.coalesce(func.max(MessageModel.sequence_no), 0) + 1).where(
            MessageModel.conversation_id == conversation_id
        )
        return int(await self.session.scalar(statement) or 1)

    def add(
        self,
        *,
        conversation_id: str,
        sequence_no: int,
        role: MessageRole,
        content: str,
        message_type: MessageType = MessageType.TEXT,
        metadata: dict[str, Any] | None = None,
    ) -> MessageModel:
        message = MessageModel(
            conversation_id=conversation_id,
            sequence_no=sequence_no,
            role=role,
            content=content,
            message_type=message_type,
            extra_data=metadata or {},
        )
        self.session.add(message)
        return message

    async def list_for_user(
        self,
        *,
        conversation_id: str,
        user_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[MessageModel]:
        """通过连接会话表校验消息确实属于当前用户。"""

        statement = (
            select(MessageModel)
            .join(ConversationModel, ConversationModel.id == MessageModel.conversation_id)
            .where(
                MessageModel.conversation_id == conversation_id,
                ConversationModel.user_id == user_id,
            )
            .order_by(MessageModel.sequence_no.asc())
            .offset(offset)
            .limit(limit)
        )
        return list((await self.session.scalars(statement)).all())

    async def list_recent_for_user(
        self,
        *,
        conversation_id: str,
        user_id: str,
        limit: int,
    ) -> list[MessageModel]:
        """读取最近 N 条消息，并在返回前恢复成从旧到新的自然顺序。"""

        statement = (
            select(MessageModel)
            .join(ConversationModel, ConversationModel.id == MessageModel.conversation_id)
            .where(
                MessageModel.conversation_id == conversation_id,
                ConversationModel.user_id == user_id,
            )
            .order_by(MessageModel.sequence_no.desc())
            .limit(limit)
        )
        newest_first = list((await self.session.scalars(statement)).all())
        newest_first.reverse()
        return newest_first

    async def list_after_sequence_for_user(
        self,
        *,
        conversation_id: str,
        user_id: str,
        after_sequence: int,
        limit: int = 500,
    ) -> list[MessageModel]:
        """读取摘要游标之后的消息，供上下文压缩使用。"""

        statement = (
            select(MessageModel)
            .join(ConversationModel, ConversationModel.id == MessageModel.conversation_id)
            .where(
                MessageModel.conversation_id == conversation_id,
                ConversationModel.user_id == user_id,
                MessageModel.sequence_no > after_sequence,
            )
            .order_by(MessageModel.sequence_no.asc())
            .limit(limit)
        )
        return list((await self.session.scalars(statement)).all())
