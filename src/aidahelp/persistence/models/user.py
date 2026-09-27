"""客服用户 ORM 模型。"""

from sqlalchemy import Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from aidahelp.domain.enums import UserStatus, enum_values
from aidahelp.persistence.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class UserModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """单企业中的终端用户。

    ``external_user_id`` 对接商城、微信或 CRM 的用户编号，是外部系统与 AidaHelp 的桥梁。
    """

    __tablename__ = "users"

    external_user_id: Mapped[str] = mapped_column(
        String(128),
        unique=True,
        index=True,
        nullable=False,
    )
    nickname: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[UserStatus] = mapped_column(
        Enum(
            UserStatus,
            name="user_status",
            native_enum=False,
            create_constraint=True,
            values_callable=enum_values,
            length=32,
        ),
        default=UserStatus.ACTIVE,
        server_default=UserStatus.ACTIVE.value,
        index=True,
        nullable=False,
    )
