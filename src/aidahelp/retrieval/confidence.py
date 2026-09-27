"""根据精排结果计算无需额外模型调用的证据置信度。"""

from dataclasses import dataclass

KEY_TERMS = ("退款", "退货", "运费", "邮费", "保修", "赔偿", "期限", "发货")


@dataclass(frozen=True, slots=True)
class EvidenceConfidence:
    score: float
    signals: dict[str, float | int | bool]


def compute_confidence(
    scores: list[float], texts: list[str], valid_floor: float
) -> EvidenceConfidence:
    if not scores:
        return EvidenceConfidence(
            score=0.0,
            signals={"top1_score": 0.0, "valid_count": 0, "margin": 0.0, "key_hit": False},
        )
    top1 = _clip(scores[0])
    margin = top1 - _clip(scores[1]) if len(scores) > 1 else top1
    valid_count = sum(score >= valid_floor for score in scores)
    key_hit = any(term in text for text in texts[:3] for term in KEY_TERMS)
    score = 0.5 * top1 + 0.2 * min(valid_count, 3) / 3 + 0.2 * _clip(margin) + 0.1 * int(key_hit)
    return EvidenceConfidence(
        score=round(_clip(score), 4),
        signals={
            "top1_score": round(top1, 4),
            "valid_count": valid_count,
            "margin": round(margin, 4),
            "key_hit": key_hit,
        },
    )


def _clip(value: float) -> float:
    return max(0.0, min(1.0, float(value)))
