"""把完整聊天记录整理成“滚动摘要 + 最近原文”的模型上下文。"""

import hashlib
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from aidahelp.config import Settings
from aidahelp.integrations.llm.base import ChatMessage
from aidahelp.memory.summarizer import update_summary
from aidahelp.persistence.repositories.memory_repository import MemoryRepository
from aidahelp.persistence.repositories.message_repository import MessageRepository


@dataclass(frozen=True, slots=True)
class ContextWindow:
    summary: str
    messages: list[ChatMessage]
    facts: dict
    summary_until_sequence: int
    prompt_cache_key: str


class MemoryService:
    """模型上下文是压缩视图，MySQL messages 才是不可丢失的原始记录。"""

    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.memories = MemoryRepository(session)
        self.messages = MessageRepository(session)

    async def build_context(self, *, conversation_id: str, user_id: str) -> ContextWindow:
        async with self.session.begin():
            memory = await self.memories.get_or_create(conversation_id)
            unsummarized = await self.messages.list_after_sequence_for_user(
                conversation_id=conversation_id,
                user_id=user_id,
                after_sequence=memory.summary_until_sequence,
            )

            # 超过阈值时，只把较早部分折叠进摘要，最近若干条继续保留原文。
            if len(unsummarized) > self.settings.memory_summary_trigger:
                old_messages = unsummarized[: -self.settings.memory_recent_messages]
                summary, new_facts = update_summary(
                    memory.rolling_summary,
                    old_messages,
                    self.settings.memory_summary_max_chars,
                )
                memory.rolling_summary = summary
                memory.summary_until_sequence = old_messages[-1].sequence_no
                memory.facts = {**memory.facts, **new_facts}
                unsummarized = unsummarized[-self.settings.memory_recent_messages :]

            recent = unsummarized[-self.settings.memory_recent_messages :]
            model_messages = [
                ChatMessage(
                    role=item.role.value,
                    content=item.content[: self.settings.memory_message_max_chars],
                )
                for item in recent
                if item.role.value in {"user", "assistant", "tool"}
            ]
            stable_prefix = f"{memory.rolling_summary}\n{memory.facts}"
            cache_key = hashlib.sha256(stable_prefix.encode("utf-8")).hexdigest()
            memory.prompt_cache_key = cache_key

        return ContextWindow(
            summary=memory.rolling_summary,
            messages=model_messages,
            facts=dict(memory.facts),
            summary_until_sequence=memory.summary_until_sequence,
            prompt_cache_key=cache_key,
        )
