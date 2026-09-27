"""检查当前配置的数据库是否可连接。"""

import asyncio

from aidahelp.config import get_settings
from aidahelp.persistence.database import Database


async def main() -> None:
    database = Database(get_settings())
    try:
        ready = await database.ping()
        print(f"数据库地址：{database.safe_url}")
        print("数据库连接：成功" if ready else "数据库连接：失败")
        if not ready:
            raise SystemExit(1)
    finally:
        await database.dispose()


if __name__ == "__main__":
    asyncio.run(main())
