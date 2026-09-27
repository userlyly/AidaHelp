"""真实 MySQL 连接测试；未配置测试库时自动跳过。"""

import os

import pytest

from aidahelp.config import Settings
from aidahelp.persistence.database import Database


@pytest.mark.integration
@pytest.mark.anyio
async def test_mysql_can_execute_select_one() -> None:
    database_url = os.getenv("AIDAHELP_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("未设置 AIDAHELP_TEST_DATABASE_URL")

    database = Database(Settings(environment="testing", database_url=database_url))
    try:
        assert await database.ping() is True
    finally:
        await database.dispose()
