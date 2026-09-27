"""向已完成迁移的数据库写入可重复执行的演示数据。"""

import asyncio
import hashlib

from aidahelp.config import get_settings
from aidahelp.domain.enums import DocumentStatus
from aidahelp.persistence.database import Database
from aidahelp.persistence.repositories.knowledge_repository import KnowledgeRepository
from aidahelp.persistence.repositories.user_repository import UserRepository

DEMO_KNOWLEDGE = """# 七天无理由退货

商品签收后七天内，在商品完好且不影响二次销售的情况下，可以申请无理由退货。
质量问题产生的退货运费由商家承担，非质量问题的退货运费由用户承担。
"""


async def main() -> None:
    database = Database(get_settings())
    try:
        if not await database.ping():
            raise RuntimeError("数据库不可用，请先启动 MySQL 并执行 alembic upgrade head")

        async with database.session() as session:
            users = UserRepository(session)
            knowledge = KnowledgeRepository(session)
            async with session.begin():
                user = await users.get_by_external_id("demo-user")
                if user is None:
                    user = users.add(external_user_id="demo-user", nickname="演示用户")

                checksum = hashlib.sha256(DEMO_KNOWLEDGE.encode("utf-8")).hexdigest()
                document = await knowledge.get_document_by_version(
                    checksum=checksum,
                    version="demo-v1",
                )
                if document is None:
                    document = knowledge.add_document(
                        title="七天无理由退货政策",
                        source_type="markdown",
                        source_uri="seed://returns-policy",
                        content=DEMO_KNOWLEDGE,
                        checksum=checksum,
                        version="demo-v1",
                        status=DocumentStatus.PUBLISHED,
                        metadata={"category": "after_sales"},
                    )
                await session.flush()

            print(f"演示用户 ID：{user.id}")
            print(f"演示知识文档 ID：{document.id}")
            print("演示数据准备完成；重复执行不会创建重复用户或重复文档。")
    finally:
        await database.dispose()


if __name__ == "__main__":
    asyncio.run(main())
