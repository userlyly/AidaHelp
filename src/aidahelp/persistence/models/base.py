"""所有 SQLAlchemy ORM 模型共用的基类和字段。"""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import DateTime, MetaData, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# 约束采用稳定名称后，Alembic 才能可靠地生成和删除索引、外键与唯一约束。
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_name)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


def utc_now() -> datetime:
    """统一使用 UTC 保存时间，展示给用户时再转换到具体时区。"""

    return datetime.now(UTC)


def new_uuid() -> str:
    """生成字符串 UUID；相比自增数字，它不会暴露系统中已有多少条数据。"""

    return str(uuid4())


class Base(DeclarativeBase):
    """项目中所有 ORM Model 的父类。"""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class UUIDPrimaryKeyMixin:
    """统一的 UUID 主键。为便于初学者查看，阶段 2 使用可读的 CHAR(36)。"""

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)


class TimestampMixin:
    """统一的创建时间和更新时间。"""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        server_default=func.now(),
        nullable=False,
    )
