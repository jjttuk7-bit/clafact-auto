"""Conservative repair of validated Structured Outputs before official replay."""

from datetime import date
import re

from core.claim_contract import assess_claim_contract
from core.claim_time_resolver import resolve_relative_time
from core.deterministic_slot_enricher import infer_explicit_slots


_REVALIDATABLE_REASONS = {"AMBIGUOUS_COMPARISON"}
_UNRESOLVED_TIME_MARKERS = ("\uac19\uc740 \uae30\uac04", "\uc774 \uae30\uac04", "\ucd5c\uadfc", "\uc774\ubc88")


def recover_validated_claim(claim, article_date: date | None, *, source_value_text: str | None = None):
    """Re-admit only source-backed Claims that satisfy the executable contract."""
    was_auto = claim.parse_status == "AUTO_OK"
    recovered = resolve_relative_time(claim, article_date)
    comparison_type = str((recovered.comparison or {}).get("type", "")).upper()
    if (
        comparison_type in {"RECORD_HIGH", "RECORD_LOW"}
        and recovered.calculation != comparison_type
    ):
        return recovered.model_copy(update={"parse_status": "HOLD", "parse_reason": "RECORD_COMPARISON_REQUIRES_SEPARATE_CLAIM"})
    if any(marker in (recovered.time or "") for marker in _UNRESOLVED_TIME_MARKERS):
        return recovered.model_copy(update={"parse_status": "HOLD", "parse_reason": "RELATIVE_TIME_UNRESOLVED"})
    if recovered.value is None or not recovered.unit:
        return recovered
    grounding_text = source_value_text if source_value_text is not None else (None if was_auto else recovered.source_sentence)
    if grounding_text is not None and not _source_supports_claim_value(recovered, grounding_text):
        return recovered.model_copy(update={"parse_status": "HOLD", "parse_reason": "TARGET_VALUE_NOT_IN_SOURCE_SENTENCE"})
    if recovered.parse_status == "AUTO_OK":
        decision = assess_claim_contract(recovered)
        if decision.status == "PASS":
            return recovered
        return recovered.model_copy(update={"parse_status": "HOLD", "parse_reason": decision.reason_code})

    reason = (recovered.parse_reason or "").strip()
    can_repair_difference = recovered.calculation == "DIFFERENCE" and reason.startswith("MISSING_REQUIRED_SLOTS:comparison")
    if reason not in _REVALIDATABLE_REASONS and not can_repair_difference:
        return claim

    comparison = dict(recovered.comparison or {})
    if can_repair_difference:
        explicit = infer_explicit_slots(recovered.source_sentence)
        for key, value in (explicit.comparison or {}).items():
            comparison.setdefault(key, value)
        if comparison.get("current_value") and comparison.get("reference_value"):
            comparison.setdefault("operand_unit", recovered.unit or "")
    candidate = recovered.model_copy(update={"comparison": comparison or claim.comparison, "parse_status": "AUTO_OK", "parse_reason": None})
    decision = assess_claim_contract(candidate)
    if decision.status == "HOLD":
        return candidate.model_copy(update={"parse_status": "HOLD", "parse_reason": decision.reason_code})
    return candidate


_NUMBER_EXPRESSION = re.compile(r"\d+(?:[,.]\d+)*(?:(?:\uc870|\uc5b5|\ub9cc|\ucc9c)\d*(?:[,.]\d+)*)*")
_SCALES = {"\uc870": 1e12, "\uc5b5": 1e8, "\ub9cc": 1e4, "\ucc9c": 1e3}
_UNIT_BOUNDARY_PREFIXES = (
    "\uc774\uc5c8\ub2e4", "\uc600\ub2e4", "\uc774\uba70", "\uc774\uace0", "\uc73c\ub85c", "\uc5d0\uc11c", "\ubcf4\ub2e4", "\uac00\ub7c9", "\uc815\ub3c4",
    "\uc99d\uac00", "\uac10\uc18c", "\uc0c1\uc2b9", "\ud558\ub77d", "\ub298", "\uc904", "\uae30\ub85d",
    "\ub85c", "\uc740", "\ub294", "\uc774", "\uac00", "\uc744", "\ub97c", "\uc758", "\uc5d0", "\uc640", "\uacfc", "\ub9cc", "\ub354", "\uc529",
)
_INDEX_BASIS = re.compile(r"(?P<year>\d{4})(?:\ub144)?[=\uff1d]100", re.IGNORECASE)


def _source_supports_claim_value(claim, source_text: str) -> bool:
    if claim.value is None or not claim.unit:
        return False
    claim_scale, claim_base = _unit_scale_and_base(claim.unit)
    expected = abs(float(claim.value)) * claim_scale
    compact_source = source_text.replace(" ", "")
    for match in _NUMBER_EXPRESSION.finditer(compact_source):
        number = _parse_scaled_number(match.group())
        unit_tail = compact_source[match.end():]
        if _index_basis_matches(claim.unit, unit_tail) and _numbers_equal(number, expected):
            return True
        for end in range(1, min(len(unit_tail), 24) + 1):
            expression_scale, expression_base = _unit_scale_and_base(unit_tail[:end])
            if expression_base != claim_base:
                continue
            actual = number * expression_scale
            if _unit_is_bounded(unit_tail, end) and _numbers_equal(actual, expected):
                return True
    return False


def _numbers_equal(actual: float, expected: float) -> bool:
    return abs(actual - expected) <= max(1e-9, abs(expected) * 1e-9)


def _unit_is_bounded(unit_tail: str, unit_end: int) -> bool:
    remainder = unit_tail[unit_end:]
    if not remainder:
        return True
    if not remainder[0].isalnum() and remainder[0] != "_":
        return True
    return any(remainder.startswith(prefix) for prefix in _UNIT_BOUNDARY_PREFIXES)


def _index_basis_matches(unit: str, unit_tail: str) -> bool:
    claim_basis = _INDEX_BASIS.fullmatch(unit.replace(" ", ""))
    if claim_basis is None:
        return False
    source_basis = _INDEX_BASIS.search(unit_tail)
    return source_basis is not None and source_basis.group("year") == claim_basis.group("year")


def _parse_scaled_number(raw: str) -> float:
    compact = raw.replace(",", "")
    if not any(scale in compact for scale in _SCALES):
        return float(compact)
    total, remainder = 0.0, compact
    for marker, scale in (("\uc870", 1e12), ("\uc5b5", 1e8), ("\ub9cc", 1e4)):
        if marker in remainder:
            group, remainder = remainder.split(marker, 1)
            total += _parse_small_group(group) * scale
    total += _parse_small_group(remainder)
    return total


def _parse_small_group(raw: str) -> float:
    if not raw:
        return 0.0
    total, remainder = 0.0, raw
    for marker, scale in (("\ucc9c", 1e3), ("\ubc31", 1e2), ("\uc2ed", 1e1)):
        if marker in remainder:
            group, remainder = remainder.split(marker, 1)
            total += (float(group) if group else 1.0) * scale
    return total + (float(remainder) if remainder else 0.0)


def _unit_scale_and_base(unit: str) -> tuple[float, str]:
    compact = unit.replace(" ", "").strip().casefold()
    compact = {"\u33ca": "ha", "\ud37c\uc13c\ud2b8\ud3ec\uc778\ud2b8": "%\ud3ec\uc778\ud2b8", "%p": "%\ud3ec\uc778\ud2b8"}.get(compact, compact)
    if compact in {"usd100m", "100musd"}:
        return 1e8, "usd"
    for prefix, scale in (("\uc870", 1e12), ("\uc5b5", 1e8), ("\ub9cc", 1e4), ("\ucc9c", 1e3)):
        if compact.startswith(prefix) and len(compact) > len(prefix):
            base = compact[len(prefix):]
            return scale, {"\ub2ec\ub7ec": "usd", "\ud5e5\ud0c0\ub974": "ha"}.get(base, base)
    return 1.0, {"\ub2ec\ub7ec": "usd", "\ud5e5\ud0c0\ub974": "ha"}.get(compact, compact)
