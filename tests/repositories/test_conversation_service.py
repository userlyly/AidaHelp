"""会话事务、消息顺序与原文持久化测试。"""

from pathlib import Path

import pytest

from aidahelp.config import Settings
from aidahelp.domain.enums import MessageRole
from aidahelp.domain.exceptions import ConversationNotFoundError
from aidahelp.persistence.database import Database
from aidahelp.persistence.repositories.user_repository import UserRepository
from aidahelp.services.conversation_service import ConversationService


@pytest.mark.anyio
async def test_append_messages_keeps_order_and_metadata(tmp_path: Path) -> None:
    settings = Settings(
        environment="testing",
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'service.db').as_posix()}",
        database_auto_create_schema=True,
    )
    database = Database(settings)
    await database.create_schema_for_tests()

    async with database.session() as session:
        users = UserRepository(session)
        async with session.begin():
            user = users.add(external_user_id="service-user")
            await session.flush()

        service = ConversationService(session)
        conversation = await service.create_conversation(user_id=user.id, title="退货咨询")
        first = await service.append_message(
            conversation_id=conversation.id,
            user_id=user.id,
            role=MessageRole.USER,
            content="这个商品可以退吗？",
            metadata={"channel": "web"},
        )
        second = await service.append_message(
            conversation_id=conversation.id,
            user_id=user.id,
            role=MessageRole.ASSISTANT,
            content="满足条件时支持七天无理由退货。",
        )
        messages = await service.list_messages(
            conversation_id=conversation.id,
            user_id=user.id,
        )

        assert [first.sequence_no, second.sequence_no] == [1, 2]
        assert [message.content for message in messages] == [
            "这个商品可以退吗？",
            "满足条件时支持七天无理由退货。",
        ]
        assert messages[0].extra_data == {"channel": "web"}

    await database.dispose()


@pytest.mark.anyio
async def test_user_cannot_list_other_users_messages(tmp_path: Path) -> None:
    settings = Settings(
        environment="testing",
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'isolation.db').as_posix()}",
        database_auto_create_schema=True,
    )
    database = Database(settings)
    await database.create_schema_for_tests()

    async with database.session() as session:
        users = UserRepository(session)
        async with session.begin():
            owner = users.add(external_user_id="owner-service")
            other = users.add(external_user_id="other-service")
            await session.flush()

        service = ConversationService(session)
        conversation = await service.create_conversation(user_id=owner.id)
        with pytest.raises(ConversationNotFoundError):
            await service.list_messages(
                conversation_id=conversation.id,
                user_id=other.id,
            )

    await database.dispose()
