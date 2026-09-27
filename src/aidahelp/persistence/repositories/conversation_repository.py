"""会话数据访问。"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aidahelp.domain.enums import ConversationStatus
from aidahelp.persistence.models.conversation import ConversationModel


class ConversationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def add(self, *, user_id: str, title: str | None = None) -> ConversationModel:
        conversation = ConversationModel(
            user_id=user_id,
            title=title,
            status=ConversationStatus.ACTIVE,
        )
        self.session.add(conversation)
        return conversation

    async def list_for_user(self, *, user_id: str, limit: int = 50) -> list[ConversationModel]:
        statement = (
            select(ConversationModel)
            .where(ConversationModel.user_id == user_id)
            .order_by(ConversationModel.last_message_at.desc(), ConversationModel.created_at.desc())
            .limit(limit)
        )
        return list((await self.session.scalars(statement)).all())

    async def get_for_user(
        self,
        *,
        conversation_id: str,
        user_id: str,
    ) -> ConversationModel | None:
        """同时检查 user_id，不能只凭一个会话 ID 读取别人的数据。"""

        statement = select(ConversationModel).where(
            ConversationModel.id == conversation_id,
            ConversationModel.user_id == user_id,
        )
        return await self.session.scalar(statement)

    async def lock_for_user(
        self,
        *,
        conversation_id: str,
        user_id: str,
    ) -> ConversationModel | None:
        """写消息前锁住会话行，避免并发请求分配到相同消息序号。"""

        statement = (
            select(ConversationModel)
            .where(
                ConversationModel.id == conversation_id,
                ConversationModel.user_id == user_id,
            )
            .with_for_update()
        )
        return await self.session.scalar(statement)
