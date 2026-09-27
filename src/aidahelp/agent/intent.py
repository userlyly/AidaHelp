"""客服意图识别：先用可解释规则建立稳定基线，后续可以替换为分类模型。"""

from dataclasses import dataclass
from enum import StrEnum


class Intent(StrEnum):
    KNOWLEDGE = "knowledge"
    ORDER = "order"
    LOGISTICS = "logistics"
    REFUND = "refund"
    AFTER_SALES = "after_sales"
    COMPLAINT = "complaint"
    HUMAN = "human"
    CHITCHAT = "chitchat"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class IntentResult:
    intent: Intent
    confidence: float
    matched_keywords: tuple[str, ...]


_RULES: tuple[tuple[Intent, tuple[str, ...]], ...] = (
    (Intent.HUMAN, ("转人工", "人工客服", "建工单", "客服介入")),
    (Intent.COMPLAINT, ("投诉", "举报", "态度差", "欺骗")),
    # “退款多久到账”是政策咨询；只有明确动作表达才进入会产生写操作的退款流程。
    (Intent.REFUND, ("我要退款", "申请退款", "给我退款", "帮我退款", "撤销订单", "不要了")),
    (Intent.LOGISTICS, ("物流", "快递", "到哪", "发货", "运单")),
    (Intent.ORDER, ("订单", "改地址", "取消", "付款")),
    (Intent.AFTER_SALES, ("保修", "维修", "换货", "售后")),
    (
        Intent.KNOWLEDGE,
        ("怎么", "如何", "规则", "政策", "多久", "费用", "邮费", "退货", "要钱", "寄回"),
    ),
    (Intent.CHITCHAT, ("你好", "谢谢", "在吗", "再见")),
)


def classify_intent(query: str) -> IntentResult:
    normalized = query.lower()
    for intent, keywords in _RULES:
        matched = tuple(word for word in keywords if word in normalized)
        if matched:
            return IntentResult(intent, min(0.99, 0.72 + 0.08 * len(matched)), matched)
    return IntentResult(Intent.OTHER, 0.45, ())
