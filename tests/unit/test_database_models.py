"""数据库模型结构和 Enum 实际存储值测试。"""

from pathlib import Path

import pytest
from sqlalchemy import text

from aidahelp.config import Settings
from aidahelp.domain.enums import UserStatus
from aidahelp.persistence.database import Database
from aidahelp.persistence.models import Base
from aidahelp.persistence.repositories.user_repository import UserRepository


def test_expected_tables_are_registered() -> None:
    assert set(Base.metadata.tables) == {
        "users",
        "conversations",
        "messages",
        "knowledge_documents",
        "knowledge_chunks",
    }


@pytest.mark.anyio
async def test_enum_is_stored_as_lowercase_business_value(tmp_path: Path) -> None:
    settings = Settings(
        environment="testing",
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'enum.db').as_posix()}",
        database_auto_create_schema=True,
    )
    database = Database(settings)
    await database.create_schema_for_tests()

    async with database.session() as session:
        repository = UserRepository(session)
        async with session.begin():
            repository.add(external_user_id="enum-user", status=UserStatus.ACTIVE)

        raw_value = await session.scalar(
            text("SELECT status FROM users WHERE external_user_id = 'enum-user'")
        )
        assert raw_value == "active"

    await database.dispose()
