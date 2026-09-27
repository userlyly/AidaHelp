"""用户数据访问。"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aidahelp.domain.enums import UserStatus
from aidahelp.persistence.models.user import UserModel


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, user_id: str) -> UserModel | None:
        return await self.session.get(UserModel, user_id)

    async def get_by_external_id(self, external_user_id: str) -> UserModel | None:
        statement = select(UserModel).where(UserModel.external_user_id == external_user_id)
        return await self.session.scalar(statement)

    def add(
        self,
        *,
        external_user_id: str,
        nickname: str | None = None,
        status: UserStatus = UserStatus.ACTIVE,
    ) -> UserModel:
        """把新用户放入 Session；真正写库由外层事务统一提交。"""

        user = UserModel(
            external_user_id=external_user_id,
            nickname=nickname,
            status=status,
        )
        self.session.add(user)
        return user
