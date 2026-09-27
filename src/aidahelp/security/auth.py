"""短期 Bearer Token 的签发与验证。

Demo 自己签发 HS256 Token；企业部署可在这一层替换成公司 OIDC/JWKS 验证，不影响业务代码。
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

import jwt

from aidahelp.config import Settings
from aidahelp.domain.exceptions import AuthenticationError


@dataclass(frozen=True, slots=True)
class UserPrincipal:
    user_id: str
    role: Literal["customer", "admin"] = "customer"


class TokenService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.secret = settings.auth_secret.get_secret_value()

    def issue(self, *, user_id: str, role: str = "customer") -> tuple[str, datetime]:
        now = datetime.now(UTC)
        expires_at = now + timedelta(minutes=self.settings.auth_token_ttl_minutes)
        payload = {
            "sub": user_id,
            "role": role,
            "iss": self.settings.auth_issuer,
            "aud": self.settings.auth_audience,
            "iat": now,
            "exp": expires_at,
        }
        token = jwt.encode(payload, self.secret, algorithm="HS256")
        return token, expires_at

    def verify(self, token: str) -> UserPrincipal:
        try:
            payload = jwt.decode(
                token,
                self.secret,
                algorithms=["HS256"],
                issuer=self.settings.auth_issuer,
                audience=self.settings.auth_audience,
                options={"require": ["sub", "iat", "exp", "iss", "aud"]},
            )
            role = str(payload.get("role") or "customer")
            if role not in {"customer", "admin"}:
                raise AuthenticationError("Token 中的角色不合法")
            return UserPrincipal(user_id=str(payload["sub"]), role=role)  # type: ignore[arg-type]
        except AuthenticationError:
            raise
        except jwt.PyJWTError as exc:
            raise AuthenticationError() from exc
