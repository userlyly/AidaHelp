"""认证接口结构。"""

from datetime import datetime

from pydantic import BaseModel, Field


class DemoTokenRequest(BaseModel):
    external_user_id: str = Field(default="demo-user", min_length=1, max_length=128)


class TokenData(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    user_id: str
    nickname: str | None = None
