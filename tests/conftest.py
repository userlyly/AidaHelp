"""测试公共夹具。"""

import asyncio
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from aidahelp.bootstrap import create_app
from aidahelp.config import Settings
from aidahelp.persistence.database import Database
from aidahelp.persistence.repositories.user_repository import UserRepository

OWNER_USER_ID = "00000000-0000-0000-0000-000000000001"
OTHER_USER_ID = "00000000-0000-0000-0000-000000000002"


def _test_settings(database_file: Path) -> Settings:
    """每个测试使用独立 SQLite 文件，不依赖本机 MySQL。"""

    return Settings(
        environment="testing",
        log_level="CRITICAL",
        docs_enabled=True,
        database_url=f"sqlite+aiosqlite:///{database_file.as_posix()}",
        database_auto_create_schema=True,
    )


async def _prepare_users(settings: Settings) -> None:
    """直接通过 Repository 准备测试用户，不为了测试而增加公开用户接口。"""

    database = Database(settings)
    await database.create_schema_for_tests()
    async with database.session() as session:
        repository = UserRepository(session)
        async with session.begin():
            owner = repository.add(external_user_id="owner", nickname="会话所有者")
            owner.id = OWNER_USER_ID
            other = repository.add(external_user_id="other", nickname="其他用户")
            other.id = OTHER_USER_ID
    await database.dispose()


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    """每个测试创建独立应用，避免配置和应用状态互相污染。"""

    settings = _test_settings(tmp_path / "health.db")
    app = create_app(settings)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def seeded_client(tmp_path: Path) -> Iterator[TestClient]:
    """带两个用户的 API 客户端，用于验证用户数据隔离。"""

    settings = _test_settings(tmp_path / "conversations.db")
    asyncio.run(_prepare_users(settings))
    app = create_app(settings)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def anyio_backend() -> str:
    """异步测试统一使用 asyncio，避免测试框架额外尝试 trio。"""

    return "asyncio"
