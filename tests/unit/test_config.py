"""配置校验测试。"""

import pytest
from pydantic import ValidationError

from aidahelp.config import Settings


def test_api_prefix_is_normalized() -> None:
    settings = Settings(api_prefix="/service/v1/")

    assert settings.api_prefix == "/service/v1"


def test_invalid_api_prefix_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(api_prefix="api/v1")


def test_log_level_is_normalized() -> None:
    settings = Settings(log_level="warning")

    assert settings.log_level == "WARNING"
