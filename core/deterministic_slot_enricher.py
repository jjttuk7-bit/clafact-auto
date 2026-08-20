"""Conservative extraction of explicitly stated calculation-related claim slots."""

from dataclasses import dataclass
import re

from schemas.claim import ClaimSchema


_DIRECTIONAL_SIGNALS = ("증가", "감소", "상승", "하락", "늘었", "줄었")
_YEAR_OVER_YEAR_SIGNALS = (
    "전년 동월 대비",
    "전년 대비",
    "작년 동월 대비",
    "작년 대비",
    "전년 같은 기간",
    "지난해 같은 기간",
    "전년 동월보다",
    "작년 같은 달",
    "1년 새",
)
_MONTH_OVER_MONTH_SIGNALS = ("전월 대비", "지난달 대비")
_QUARTER_OVER_QUARTER_SIGNALS = ("전분기 대비", "직전 분기 대비")
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
    if len(_comparison_types(source_sentence)) > 1:
        return ExplicitSlotValues(reason_code="AMBIGUOUS_COMPARISON")
    if any(signal in source_sentence for signal in _YEAR_OVER_YEAR_SIGNALS) or (
        "작년" in source_sentence and "에 비해" in source_sentence
    ):
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
    if any(signal in source_sentence for signal in _QUARTER_OVER_QUARTER_SIGNALS):
        return ExplicitSlotValues(
            comparison={"type": "QUARTER_OVER_QUARTER"},
            calculation="GROWTH_RATE",
            condition=condition,
        )
    if any(signal in source_sentence for signal in _SHARE_SIGNALS) or re.search(r"전체.+의\s*[-+]?\d+(?:\.\d+)?\s*%", source_sentence):
        return ExplicitSlotValues(
            comparison=_explicit_share_comparison(source_sentence),
            calculation="SHARE",
            condition=condition,
        )
    if any(signal in source_sentence for signal in _DIRECTIONAL_SIGNALS):
        return ExplicitSlotValues(condition=None, reason_code="AMBIGUOUS_COMPARISON")
    return ExplicitSlotValues(calculation="DIRECT_VALUE", condition=condition)


def _explicit_share_comparison(source_sentence: str) -> dict[str, str]:
    """Return share operands only when the sentence explicitly names both sides."""
    match = re.search(
        r"(?P<numerator>.+?)는\s*(?P<denominator>전체\s*.+?)의\s*[-+]?\d+(?:\.\d+)?\s*%",
        source_sentence,
    )
    if match is None:
        return {"type": "SHARE_OF_TOTAL"}
    numerator = re.sub(r"^\s*\d{4}년(?:\s*\d{1,2}월)?\s*", "", match["numerator"]).strip()
    denominator = match["denominator"].strip()
    if not numerator or not denominator:
        return {"type": "SHARE_OF_TOTAL"}
    return {
        "type": "SHARE_OF_TOTAL",
        "numerator": numerator,
        "denominator": denominator,
        "denominator_member": "전체",
    }

def _condition(source_sentence: str) -> dict[str, str] | None:
    if "계절조정" in source_sentence:
        return {"seasonal_adjustment": "계절조정"}
    if "잠정" in source_sentence:
        return {"release_status": "잠정"}
    if "확정" in source_sentence:
        return {"release_status": "확정"}
    return None


def _comparison_types(source_sentence: str) -> set[str]:
    types: set[str] = set()
    if any(signal in source_sentence for signal in _YEAR_OVER_YEAR_SIGNALS) or (
        "작년" in source_sentence and "에 비해" in source_sentence
    ):
        types.add("YEAR_OVER_YEAR")
    if any(signal in source_sentence for signal in _MONTH_OVER_MONTH_SIGNALS):
        types.add("MONTH_OVER_MONTH")
    if any(signal in source_sentence for signal in _QUARTER_OVER_QUARTER_SIGNALS):
        types.add("QUARTER_OVER_QUARTER")
    return types

def _with_explicit_dimension_members(claim: ClaimSchema) -> dict[str, str]:
    """Move explicitly named sex/age values into their dedicated 12-slot axes."""
    dimension = dict(claim.dimension or {})
    source = f"{claim.population or ''} {claim.source_sentence}"
    if "sex" not in dimension:
        if "여성" in source or "여자" in source:
            dimension["sex"] = "여성"
        elif "남성" in source or "남자" in source:
            dimension["sex"] = "남성"
    if "age" not in dimension:
        match = re.search(r"(?P<start>\d{1,2})\s*(?:~|[-–])\s*(?P<end>\d{1,2})\s*세", source)
        if match:
            dimension["age"] = f"{match.group('start')}~{match.group('end')}세"
    return dimension
def _direction_matches(source_sentence: str) -> list[tuple[int, str]]:
    patterns = (
        ("INCREASE", r"\uc99d\uac00(?:\ud588\ub2e4|\ud588[\uace0\uc73c\uba70]*|\ud55c|\ud574)|\uc0c1\uc2b9(?:\ud588\ub2e4|\ud588[\uace0\uc73c\uba70]*|\ud55c|\ud574)|\ub298\uc5c8|\ub298\uc5b4|\uc62c\ub790|\ubd88\uc5b4"),
        ("DECREASE", r"\uac10\uc18c(?:\ud588\ub2e4|\ud588[\uace0\uc73c\uba70]*|\ud55c|\ud574)|\ud558\ub77d(?:\ud588\ub2e4|\ud588[\uace0\uc73c\uba70]*|\ud55c|\ud574)|\uc904\uc5c8|\uc904\uc5b4|\ub0b4\ub838"),
    )
    return [
        (match.start(), direction)
        for direction, pattern in patterns
        for match in re.finditer(pattern, source_sentence)
    ]


def _direction(source_sentence: str) -> str | None:
    predicates = _direction_matches(source_sentence)
    if not predicates:
        return None
    return max(predicates, key=lambda item: item[0])[1]


def apply_explicit_slots(claim: ClaimSchema) -> ClaimSchema:
    """Fill only missing comparison/condition fields explicitly stated in source."""
    explicit = infer_explicit_slots(claim.source_sentence)
    directions = {direction for _, direction in _direction_matches(claim.source_sentence)}
    if (
        explicit.reason_code == "AMBIGUOUS_COMPARISON" and not claim.comparison
    ) or len(directions) > 1:
        return claim.model_copy(update={
            "parse_status": "HOLD",
            "parse_reason": "AMBIGUOUS_COMPARISON",
        })
    comparison = dict(claim.comparison or {})
    condition = dict(claim.condition or {})
    for key, value in (explicit.comparison or {}).items():
        comparison.setdefault(key, value)
    if (
        (explicit.comparison or {}).get("type") == "SHARE_OF_TOTAL"
        and str(comparison.get("type", "")).strip().upper() == "SHARE"
    ):
        comparison["type"] = "SHARE_OF_TOTAL"
    for key, value in (explicit.condition or {}).items():
        condition.setdefault(key, value)
    if (direction := _direction(claim.source_sentence)) is not None:
        condition.setdefault("direction", direction)
    dimension = _with_explicit_dimension_members(claim)
    return claim.model_copy(update={
        "dimension": dimension or claim.dimension,
        "comparison": comparison or claim.comparison,
        "calculation": claim.calculation or explicit.calculation,
        "condition": condition or claim.condition,
    })