"""Source-span grounded sign and direction preservation for Claim targets."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Mapping

from schemas.claim_registry import ClaimRegistryRecord


_INCREASE = re.compile(r"급증|증가|상승|늘(?:었|어|어난|렸|리|고)|올랐|오르|뛰(?:었|어)|불어")
_DECREASE = re.compile(r"급감|감소|하락|줄(?:었|어|어든|였|이|며)|내렸|내리|둔화")
_CHANGE_HEAD = re.compile(r"(?P<cue>증가|감소)\s*(?:폭|규모)")
_LEVEL_AFTER_TARGET = re.compile(
    r"^\s*(?:\)|\])?(?:을|를|이|가|은|는)?\s*"
    r"(?:정점|수준|선|대(?:로|에)?|까지|기록)"
)
_COUNTED_CHANGE_NOUN = re.compile(
    r"(?:증가|감소)\s*(?:지역|품목|국가|채널|업종|기업)[^,.!?。]{0,16}$"
)
_BLOCK_REASONS = {
    "TARGET_ROLE_REVIEW_REQUIRED": "TARGET_ROLE_REVIEW_REQUIRED",
    "DIRECTION_AMBIGUOUS": "SOURCE_DIRECTION_AMBIGUOUS",
}


@dataclass(frozen=True, slots=True)
class SourceSignDirectionDecision:
    status: str
    reason_code: str
    original_value: float
    signed_target_value: float | None
    source_direction: str = ""
    source_polarity: str = ""
    basis_text: str = ""
    basis_start: int | None = None
    basis_end: int | None = None
    stored_direction: str = ""


def assess_source_sign_direction(
    *,
    source_sentence: str,
    indicator: str,
    value: float,
    target_expression: str,
    target_role: str,
    target_start: int,
    target_end: int,
    stored_condition: Mapping[str, object] | None,
) -> SourceSignDirectionDecision:
    """Resolve sign semantics only from the exact grounded target span."""

    original = float(value)
    if (
        target_start < 0
        or target_end <= target_start
        or source_sentence[target_start:target_end] != target_expression
    ):
        return _decision(
            "DIRECTION_AMBIGUOUS",
            "SOURCE_TARGET_SPAN_INVALID",
            original,
            None,
        )

    polarity = _balance_polarity(
        source_sentence, indicator, target_start, target_end
    )
    if polarity is not None:
        name, start, end = polarity
        signed = -abs(original) if name == "DEFICIT" else abs(original)
        return _decision(
            "BALANCE_POLARITY_CONFIRMED",
            "SOURCE_BALANCE_POLARITY_EXACT",
            original,
            signed,
            source_polarity=name,
            basis_text=source_sentence[start:end],
            basis_start=start,
            basis_end=end,
        )

    if _compact(target_role) != "증감값":
        return _decision(
            "NOT_APPLICABLE_LEVEL_VALUE",
            "LEVEL_VALUE_DOES_NOT_USE_SIGNED_CHANGE",
            original,
            None,
        )

    if _looks_like_level_target(source_sentence, target_start, target_end):
        return _decision(
            "TARGET_ROLE_REVIEW_REQUIRED",
            "TARGET_IS_LEVEL_NOT_CHANGE_AMOUNT",
            original,
            None,
        )

    grounded = _ground_direction(source_sentence, target_start, target_end)
    stored = _normalize_direction((stored_condition or {}).get("direction"))
    if grounded is None:
        return _decision(
            "DIRECTION_AMBIGUOUS",
            "SOURCE_DIRECTION_NOT_ATTACHED_TO_TARGET",
            original,
            None,
            stored_direction=stored,
        )
    direction, start, end = grounded
    signed = abs(original) if direction == "INCREASE" else -abs(original)
    if not stored:
        status = "SOURCE_DIRECTION_RECOVERED"
        reason = "SOURCE_DIRECTION_EXACT_TARGET"
    elif stored == direction:
        status = "SIGN_DIRECTION_CONFIRMED"
        reason = "STORED_DIRECTION_MATCHES_SOURCE"
    else:
        status = "STORED_DIRECTION_CONFLICT_CORRECTED"
        reason = "STORED_DIRECTION_REPLACED_BY_EXACT_SOURCE"
    return _decision(
        status,
        reason,
        original,
        signed,
        source_direction=direction,
        basis_text=source_sentence[start:end],
        basis_start=start,
        basis_end=end,
        stored_direction=stored,
    )


def apply_source_sign_direction_enrichment(
    record: ClaimRegistryRecord,
) -> ClaimRegistryRecord:
    """Apply only source-grounded direction slots while preserving claim.value."""

    enrichment = record.slot_enrichment or {}
    status = str(enrichment.get("sign_direction_status") or "")
    condition = dict(record.claim.condition or {})
    changed = False
    if status in {
        "SIGN_DIRECTION_CONFIRMED",
        "SOURCE_DIRECTION_RECOVERED",
        "STORED_DIRECTION_CONFLICT_CORRECTED",
    }:
        direction = str(enrichment.get("source_direction") or "")
        if direction in {"INCREASE", "DECREASE"}:
            condition["direction"] = direction
            changed = True
    if status == "BALANCE_POLARITY_CONFIRMED":
        polarity = str(enrichment.get("source_polarity") or "")
        if polarity in {"DEFICIT", "SURPLUS"}:
            condition["polarity"] = polarity
            changed = True
    if not changed:
        return record
    claim = record.claim.model_copy(update={"condition": condition})
    return record.model_copy(update={"claim": claim})


def sign_direction_preverification_reason(
    record: ClaimRegistryRecord,
) -> str | None:
    """Return structural pre-KOSIS reasons for unsafe sign decisions."""

    status = str((record.slot_enrichment or {}).get("sign_direction_status") or "")
    return _BLOCK_REASONS.get(status)


def _balance_polarity(
    source: str,
    indicator: str,
    target_start: int,
    target_end: int,
) -> tuple[str, int, int] | None:
    if "수지" not in _compact(indicator):
        return None
    start = max(0, target_start - 32)
    end = min(len(source), target_end + 24)
    window = source[start:end]
    matches = list(re.finditer(r"적자|흑자", window))
    polarities = {match.group() for match in matches}
    if not matches or len(polarities) != 1:
        return None
    match = min(
        matches,
        key=lambda item: min(abs(start + item.start() - target_end), abs(start + item.end() - target_start)),
    )
    name = "DEFICIT" if match.group() == "적자" else "SURPLUS"
    absolute_start = start + match.start()
    absolute_end = start + match.end()
    basis_start = min(target_start, absolute_start)
    basis_end = max(target_end, absolute_end)
    return name, basis_start, basis_end


def _looks_like_level_target(source: str, start: int, end: int) -> bool:
    after = source[end:min(len(source), end + 18)]
    if _LEVEL_AFTER_TARGET.search(after):
        return True
    before = source[max(0, start - 32):start]
    return _COUNTED_CHANGE_NOUN.search(before) is not None


def _ground_direction(
    source: str,
    target_start: int,
    target_end: int,
) -> tuple[str, int, int] | None:
    before_start = max(0, target_start - 32)
    before = source[before_start:target_start]
    heads = list(_CHANGE_HEAD.finditer(before))
    if heads:
        head = heads[-1]
        direction = "INCREASE" if head.group("cue") == "증가" else "DECREASE"
        return direction, before_start + head.start(), target_end
    if source[target_start:target_end].lstrip().startswith(("-", "−", "△")):
        return "DECREASE", target_start, target_end

    after = source[target_end:min(len(source), target_end + 48)]
    clause = re.split(r"[.!?。]", after, maxsplit=1)[0]
    candidates: list[tuple[int, int, str]] = []
    for pattern, direction in ((_INCREASE, "INCREASE"), (_DECREASE, "DECREASE")):
        match = pattern.search(clause)
        if match is not None:
            candidates.append((match.start(), match.end(), direction))
    if not candidates:
        return None
    cue_start, cue_end, direction = min(candidates, key=lambda item: item[0])
    between = clause[:cue_start]
    if re.search(r"\d", between):
        return None
    return direction, target_start, target_end + cue_end


def _normalize_direction(value: object) -> str:
    compact = _compact(str(value or "")).upper()
    if compact in {"INCREASE", "증가", "상승"}:
        return "INCREASE"
    if compact in {"DECREASE", "감소", "하락"}:
        return "DECREASE"
    return ""


def _compact(value: str) -> str:
    return re.sub(r"\s+", "", value or "")


def _decision(
    status: str,
    reason: str,
    original: float,
    signed: float | None,
    *,
    source_direction: str = "",
    source_polarity: str = "",
    basis_text: str = "",
    basis_start: int | None = None,
    basis_end: int | None = None,
    stored_direction: str = "",
) -> SourceSignDirectionDecision:
    return SourceSignDirectionDecision(
        status=status,
        reason_code=reason,
        original_value=original,
        signed_target_value=signed,
        source_direction=source_direction,
        source_polarity=source_polarity,
        basis_text=basis_text,
        basis_start=basis_start,
        basis_end=basis_end,
        stored_direction=stored_direction,
    )
