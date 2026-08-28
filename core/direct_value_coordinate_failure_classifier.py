"""Evidence-backed primary-cause classification for coordinate failures."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Mapping, Sequence

from core.indicator_unit_compatibility import assess_indicator_unit


@dataclass(frozen=True, slots=True)
class CoordinateFailureClassification:
    primary_cause: str
    supporting_causes: tuple[str, ...]
    rule_family: str
    evidence_codes: tuple[str, ...]


_CAUSES = {
    "FREQUENCY_CONFLICT": ("PERIOD_FREQUENCY_GAP", "OFFICIAL_PERIOD_NORMALIZATION"),
    "TIME_NOT_AVAILABLE": ("PERIOD_FREQUENCY_GAP", "OFFICIAL_PERIOD_NORMALIZATION"),
    "REGION_GRANULARITY_CONFLICT": ("REGION_COORDINATE_GAP", "OFFICIAL_REGION_ALIAS"),
    "AGE_DIMENSION_REQUIRED": ("DIMENSION_COORDINATE_GAP", "OFFICIAL_DIMENSION_MEMBER"),
    "POPULATION_DIMENSION_CONFLICT": ("DIMENSION_COORDINATE_GAP", "OFFICIAL_DIMENSION_MEMBER"),
    "DIMENSION_MEMBER_CONFLICT": ("DIMENSION_COORDINATE_GAP", "OFFICIAL_DIMENSION_MEMBER"),
    "METADATA_INCOMPLETE": ("METADATA_GAP", "OFFICIAL_METADATA_REFRESH"),
}
_PRIMARY_ORDER = (
    "FREQUENCY_CONFLICT",
    "TIME_NOT_AVAILABLE",
    "REGION_GRANULARITY_CONFLICT",
    "AGE_DIMENSION_REQUIRED",
    "POPULATION_DIMENSION_CONFLICT",
    "DIMENSION_MEMBER_CONFLICT",
    "METADATA_INCOMPLETE",
)


def classify_coordinate_failure(
    claim: Mapping[str, object],
    diagnostics: Mapping[str, object],
    candidates: Sequence[Mapping[str, object]],
) -> CoordinateFailureClassification:
    """Choose one primary cause from source slots and closest official candidates."""

    indicator = _text(claim.get("indicator"))
    unit = _text(claim.get("unit"))
    target_role = _text(claim.get("target_numeric_role"))
    decision = assess_indicator_unit(indicator, unit, target_role)
    best_codes = _best_reject_codes(diagnostics)

    if decision.status == "INDICATOR_UNIT_CONFLICT":
        return _classification(
            "CLAIM_STRUCTURE_ERROR",
            best_codes,
            "SOURCE_INDICATOR_VALUE_ROLE",
            ("INDICATOR_UNIT_MEASURE_MISMATCH",),
        )
    source_hint = _text(claim.get("source_hint"))
    if source_hint.startswith("OFFICIAL_AUTHOR"):
        return _classification(
            "NON_KOSIS_OFFICIAL_ROUTE",
            best_codes,
            "OFFICIAL_AUTHOR_ROUTE",
            ("SOURCE_HINT_OFFICIAL_AUTHOR",),
        )

    for code in _PRIMARY_ORDER:
        if code in best_codes:
            cause, rule = _CAUSES[code]
            return _classification(cause, best_codes, rule, (code,))

    if "UNIT_CONFLICT" in best_codes:
        compatibility = _candidate_unit_compatibility(unit, candidates)
        if compatibility == "SAME_MEASURE_SCALE":
            return _classification(
                "UNIT_COORDINATE_GAP",
                best_codes,
                "SAME_MEASURE_UNIT_SCALE",
                ("UNIT_CONFLICT", "SAME_MEASURE_SCALE"),
            )
        evidence = ("UNIT_CONFLICT",)
        if compatibility == "CROSS_CURRENCY":
            evidence += ("CROSS_CURRENCY_NOT_AUTOMATIC",)
        return _classification(
            "SEMANTIC_COORDINATE_AMBIGUITY",
            best_codes,
            "NO_AUTOMATIC_UNIT_CONVERSION",
            evidence,
        )

    return _classification(
        "SEMANTIC_COORDINATE_AMBIGUITY",
        best_codes,
        "EXACT_COORDINATE_REVIEW",
        ("NO_UNIQUE_COORDINATE_CAUSE",),
    )


def _classification(
    primary: str,
    best_codes: set[str],
    rule: str,
    evidence: tuple[str, ...],
) -> CoordinateFailureClassification:
    return CoordinateFailureClassification(
        primary_cause=primary,
        supporting_causes=tuple(sorted(best_codes)),
        rule_family=rule,
        evidence_codes=tuple(dict.fromkeys(evidence)),
    )


def _best_reject_codes(diagnostics: Mapping[str, object]) -> set[str]:
    prefix = "hard_guard_best_reject_"
    return {
        str(key).removeprefix(prefix)
        for key, value in diagnostics.items()
        if str(key).startswith(prefix) and _positive(value)
    }


def _candidate_unit_compatibility(
    claim_unit: str,
    candidates: Sequence[Mapping[str, object]],
) -> str:
    source_currency = _currency_family(claim_unit)
    source_measure = _measure_family(claim_unit)
    for candidate in candidates:
        units = candidate.get("unit_names") or []
        if not isinstance(units, list):
            continue
        for official_unit in units:
            target = _text(official_unit)
            if source_currency and (target_currency := _currency_family(target)):
                if source_currency == target_currency:
                    return "SAME_MEASURE_SCALE"
                return "CROSS_CURRENCY"
            if source_measure and source_measure == _measure_family(target):
                return "SAME_MEASURE_SCALE"
    return "UNRESOLVED"


def _currency_family(unit: str) -> str:
    compact = re.sub(r"\s+", "", unit).casefold()
    if compact in {"원", "만원", "억원", "조원", "천원", "백만원", "십억원"}:
        return "KRW"
    if compact in {"달러", "천달러", "만달러", "억달러", "십억달러", "천불", "천$", "usd"}:
        return "USD"
    return ""


def _measure_family(unit: str) -> str:
    compact = re.sub(r"\s+", "", unit).casefold()
    if compact in {"명", "천명", "만명"}:
        return "PERSON"
    if compact in {"가구", "천가구", "만가구"}:
        return "HOUSEHOLD"
    if compact in {"대", "천대", "만대"}:
        return "VEHICLE"
    if compact in {"톤", "천톤", "만톤", "t", "kg", "㎏"}:
        return "MASS"
    if compact in {"ha", "헥타르", "㎡", "km²", "㎢"}:
        return "AREA"
    return ""


def _positive(value: object) -> bool:
    try:
        return float(value) > 0
    except (TypeError, ValueError):
        return False


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()


__all__ = ["CoordinateFailureClassification", "classify_coordinate_failure"]
