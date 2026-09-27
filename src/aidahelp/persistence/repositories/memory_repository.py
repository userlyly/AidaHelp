"""压缩会话记忆的数据访问层。"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aidahelp.persistence.models.agent_runtime import ConversationMemoryModel


class MemoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, conversation_id: str) -> ConversationMemoryModel | None:
        return await self.session.scalar(
            select(ConversationMemoryModel).where(
                ConversationMemoryModel.conversation_id == conversation_id
            )
        )

    async def get_or_create(self, conversation_id: str) -> ConversationMemoryModel:
        memory = await self.get(conversation_id)
        if memory is None:
            memory = ConversationMemoryModel(conversation_id=conversation_id)
            self.session.add(memory)
            await self.session.flush()
        return memory
