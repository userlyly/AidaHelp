"""指代消解：让“它/这笔订单”在检索和路由前变成可独立理解的问题。"""

import re

from aidahelp.integrations.llm.base import ChatMessage

_REFERENCE = re.compile(r"(它|这个|那个|这笔|那笔|刚才|上面|前面说的)")


def resolve_reference(query: str, history: list[ChatMessage]) -> str:
    if not _REFERENCE.search(query):
        return query
    previous_user = next(
        (
            item.content
            for item in reversed(history)
            if item.role == "user" and item.content != query
        ),
        "",
    )
    if not previous_user:
        return query
    # 不偷偷改写原始消息，只构造一个供本轮下游理解的 resolved_query。
    return f"结合上一条用户问题“{previous_user[:300]}”，当前问题是：{query}"
