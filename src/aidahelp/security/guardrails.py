"""输入、外部内容和模型输出的安全护栏。"""

import re
from dataclasses import dataclass

from aidahelp.domain.exceptions import UnsafeInputError

_HIGH_RISK_INPUT = (
    re.compile(r"忽略.{0,12}(系统|之前|以上).{0,12}(提示|指令)", re.IGNORECASE),
    re.compile(
        r"(输出|告诉我|泄露|读取).{0,16}(api.?key|密钥|密码|环境变量|system prompt)", re.IGNORECASE
    ),
    re.compile(r"(绕过|取消|关闭).{0,12}(权限|审核|安全|确认)", re.IGNORECASE),
    re.compile(r"调用.{0,12}(隐藏|未注册|管理员).{0,8}工具", re.IGNORECASE),
)
_UNTRUSTED_INSTRUCTION = re.compile(
    r"(ignore previous|system message|忽略.{0,12}指令|执行以下命令|调用工具|泄露密钥)",
    re.IGNORECASE,
)
_SECRET = re.compile(r"(?i)(api[_-]?key|password|secret)\s*[:=]\s*[^\s,;]{6,}")
_EMAIL = re.compile(r"(?<![\w.-])[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}(?![\w.-])")
_PHONE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")


@dataclass(frozen=True, slots=True)
class GuardDecision:
    allowed: bool
    reason: str | None = None
    rule: str | None = None


class SecurityGuard:
    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled

    def inspect_input(self, text: str) -> GuardDecision:
        if not self.enabled:
            return GuardDecision(True)
        for index, pattern in enumerate(_HIGH_RISK_INPUT, start=1):
            if pattern.search(text):
                return GuardDecision(False, "检测到越权或提示词注入意图", f"input_rule_{index}")
        return GuardDecision(True)

    def require_safe_input(self, text: str) -> None:
        decision = self.inspect_input(text)
        if not decision.allowed:
            raise UnsafeInputError(decision.reason)

    def sanitize_untrusted(self, text: str, *, max_chars: int = 8000, wrap: bool = True) -> str:
        """知识和工具输出只能作为数据；疑似外部指令行会被剔除。"""

        safe_lines = [line for line in text.splitlines() if not _UNTRUSTED_INSTRUCTION.search(line)]
        cleaned = "\n".join(safe_lines)[:max_chars]
        return f"<UNTRUSTED_DATA>\n{cleaned}\n</UNTRUSTED_DATA>" if wrap else cleaned

    def sanitize_output(self, text: str) -> str:
        """最后一道防泄漏：屏蔽常见密钥、邮箱和手机号。"""

        if not self.enabled:
            return text
        text = _SECRET.sub(r"\1=[REDACTED]", text)
        text = _EMAIL.sub("[REDACTED_EMAIL]", text)
        return _PHONE.sub("[REDACTED_PHONE]", text)
