"""低成本、确定性的滚动摘要器。

真实项目可替换为专门的摘要模型；这里先保证不额外消耗模型 Token 也能跑通工程链路。
"""

import re

from aidahelp.persistence.models.message import MessageModel

_ORDER_ID = re.compile(r"\b(?:ORD|ORDER|AIDA)[-_]?\d{4,}\b", re.IGNORECASE)


def update_summary(previous: str, messages: list[MessageModel], max_chars: int) -> tuple[str, dict]:
    lines = [previous.strip()] if previous.strip() else []
    facts: dict[str, object] = {}
    order_ids: list[str] = []
    for message in messages:
        role = {"user": "用户", "assistant": "客服", "tool": "工具"}.get(
            message.role.value, message.role.value
        )
        compact = " ".join(message.content.split())
        lines.append(f"{role}：{compact[:240]}")
        order_ids.extend(_ORDER_ID.findall(compact))
    if order_ids:
        facts["order_ids"] = list(dict.fromkeys(item.upper() for item in order_ids))[-5:]
    summary = "\n".join(lines)
    return summary[-max_chars:], facts
