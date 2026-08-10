"""Conservative extraction of explicitly stated calculation-related claim slots."""

from dataclasses import dataclass


_DIRECTIONAL_SIGNALS = ("증가", "감소", "상승", "하락", "늘었", "줄었")
_YEAR_OVER_YEAR_SIGNALS = ("전년 동월 대비", "전년 대비", "작년 동월 대비", "작년 대비")
_MONTH_OVER_MONTH_SIGNALS = ("전월 대비", "지난달 대비")
_SHARE_SIGNALS = ("비중", "점유율", "구성비")


@dataclass(frozen=True)
class ExplicitSlotValues:
    """Only the slots supported by an explicit phrase in a source sentence."""

    comparison: dict[str, str] | None = None
    calculation: str | None = None
    condition: dict[str, str] | None = None
    reason_code: str | None = None


def infer_explicit_slots(source_sentence: str) -> ExplicitSlotValues:
    """Infer slots only when the Korean source text states their meaning explicitly."""
    condition = _condition(source_sentence)
    if any(signal in source_sentence for signal in _YEAR_OVER_YEAR_SIGNALS):
        return ExplicitSlotValues(
            comparison={"type": "YEAR_OVER_YEAR"},
            calculation="GROWTH_RATE",
            condition=condition,
        )
    if any(signal in source_sentence for signal in _MONTH_OVER_MONTH_SIGNALS):
        return ExplicitSlotValues(
            comparison={"type": "MONTH_OVER_MONTH"},
            calculation="GROWTH_RATE",
            condition=condition,
        )
    if any(signal in source_sentence for signal in _SHARE_SIGNALS):
        return ExplicitSlotValues(
            comparison={"type": "SHARE_OF_TOTAL"},
            calculation="SHARE",
            condition=condition,
        )
    if any(signal in source_sentence for signal in _DIRECTIONAL_SIGNALS):
        return ExplicitSlotValues(condition=condition, reason_code="AMBIGUOUS_COMPARISON")
    return ExplicitSlotValues(calculation="DIRECT_VALUE", condition=condition)


def _condition(source_sentence: str) -> dict[str, str] | None:
    if "계절조정" in source_sentence:
        return {"seasonal_adjustment": "계절조정"}
    if "잠정" in source_sentence:
        return {"release_status": "잠정"}
    if "확정" in source_sentence:
        return {"release_status": "확정"}
    return None
