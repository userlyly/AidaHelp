"""异步数据库 Engine、连接池与 Session 管理。"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from aidahelp.config import Settings
from aidahelp.persistence.models import Base


class Database:
    """封装数据库连接池。

    Engine 是进程级对象，负责管理连接池；Session 是请求级对象，不能在请求之间共享。
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        url = make_url(settings.database_url)
        self.is_sqlite = url.get_backend_name() == "sqlite"

        engine_options: dict[str, object] = {
            "echo": settings.database_echo,
            "pool_pre_ping": True,
        }
        if self.is_sqlite:
            # SQLite 仅用于测试；check_same_thread=False 允许 TestClient 跨线程访问测试文件。
            engine_options["connect_args"] = {"check_same_thread": False}
        else:
            engine_options.update(
                pool_size=settings.database_pool_size,
                max_overflow=settings.database_max_overflow,
                pool_recycle=settings.database_pool_recycle,
                connect_args={"connect_timeout": settings.database_connect_timeout},
            )

        self.engine: AsyncEngine = create_async_engine(settings.database_url, **engine_options)
        self.session_factory = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )

    @property
    def safe_url(self) -> str:
        """隐藏密码后的数据库地址，可以安全地写入日志。"""

        return make_url(self.settings.database_url).render_as_string(hide_password=True)

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        """创建请求级 Session；异常时回滚尚未提交的事务。"""

        async with self.session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    async def ping(self) -> bool:
        """执行最小查询，用于就绪检查。"""

        try:
            async with self.engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    async def create_schema_for_tests(self) -> None:
        """只为测试自动建表；正常环境必须运行 Alembic。"""

        if not (
            self.settings.environment == "testing" and self.settings.database_auto_create_schema
        ):
            raise RuntimeError("自动建表只允许在 testing 环境显式开启")
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def dispose(self) -> None:
        """应用停止时关闭连接池。"""

        await self.engine.dispose()
