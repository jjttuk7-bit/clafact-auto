"""Deterministic verification-type guard for type-8 direct-value targets."""

from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True, slots=True)
class DirectValueTypeDecision:
    type_code: str
    reason_code: str | None


_RATE_UNITS = {"%", "％", "퍼센트"}
_SHARE = re.compile(r"(?:비중|구성비|점유율|차지|전체의\s*\d)")
_RECORD = re.compile(
    r"(?:역대|사상|최대|최소|최고|최저|고점|저점|처음|최초|"
    r"\d+년\s*만|\d+개월\s*만|통계\s*작성\s*이래)"
)
_RANK = re.compile(r"(?:\d+위|순위|전국에서\s*가장|가장\s*(?:높|낮))")
_CHANGE = re.compile(
    r"(?:급감|급증|증가|감소|상승|하락|늘(?:었|어|어난|었다|린)|"
    r"줄(?:었|어|어든|었다|인)|올랐|오른|오르|내렸|내린|내리|"
    r"뒷걸음|개선|악화|인상|인하|끌어올|끌어내|높였|낮췄)"
)
_LEVEL_CONNECTOR = re.compile(
    r"^\s*(?:까지|대로|수준(?:으로|일|이|에)?|선(?:으로|에)?|로|으로)\s*"
)
_THRESHOLD = re.compile(r"(?:이상|이하|미만|초과|넘(?:었|어|는|어서)|밑돌|못\s*미치|아래로|돌파)")
_CURRENT_RECORD_TAIL = re.compile(r"(?:역대|사상|통계\s*작성\s*이래|\d{4}년(?:\s*\d{1,2}월)?\s*이후).{0,20}(?:최고|최저|가장\s*(?:높|낮)|최대|최소)")
_REGIONAL_RANK_TAIL = re.compile(r"(?:전국|지역|시도|17개\s*시도).{0,14}(?:가장\s*(?:높|낮)|\d+위)|(?:\d+위|순위)")


def classify_direct_value_target(
    source_sentence: str,
    *,
    target_expression: str,
    unit: str,
    indicator: str,
) -> DirectValueTypeDecision:
    """Keep only one-cell level/threshold Claims in the type-8 lane."""

    clause, target_offset, target_length = _target_clause(source_sentence, target_expression)
    if target_offset < 0:
        return DirectValueTypeDecision("REVIEW", "TARGET_VALUE_NOT_IN_SOURCE_SENTENCE")
    prefix = clause[:target_offset]
    tail = clause[target_offset + target_length:]
    if _SHARE.search(prefix[-32:] + target_expression + tail[:20]):
        return DirectValueTypeDecision("SHARE", "RECLASSIFY_TO_SHARE")

    if re.match(r"^\s*[)）]?\s*이후", tail):
        return DirectValueTypeDecision("RECORD", "RECLASSIFY_TO_RECORD")
    change_tail = _LEVEL_CONNECTOR.sub("", tail, count=1)
    level_connector_present = change_tail != tail
    change_is_target = bool(_CHANGE.search(tail[:32])) and not level_connector_present
    if change_is_target:
        if re.sub(r"\s+", "", unit) in _RATE_UNITS:
            return DirectValueTypeDecision(
                "GROWTH_RATE", "RECLASSIFY_TO_GROWTH_RATE"
            )
        return DirectValueTypeDecision("DIFFERENCE", "RECLASSIFY_TO_DIFFERENCE")
    if _REGIONAL_RANK_TAIL.search(tail[:48]):
        return DirectValueTypeDecision("RANK", "RECLASSIFY_TO_RANK")
    if _CURRENT_RECORD_TAIL.search(tail[:48]) and not _CHANGE.search(tail[:48]):
        return DirectValueTypeDecision("RECORD", "RECLASSIFY_TO_RECORD")
    if level_connector_present:
        return DirectValueTypeDecision("DIRECT_VALUE", None)
    if _THRESHOLD.search(tail[:32]) or "돌파" in tail[:24]:
        return DirectValueTypeDecision("THRESHOLD", None)
    if re.match(
        r"^\s*(?:은|는|이|가|을|를)?\s*(?:흑자|적자)?\s*"
        r"(?:로|으로|이다|였다|수준|규모|집계|기록)",
        tail,
    ):
        return DirectValueTypeDecision("DIRECT_VALUE", None)
    if "이후" in tail[:32] or _RECORD.search(prefix[-36:]):
        return DirectValueTypeDecision("RECORD", "RECLASSIFY_TO_RECORD")
    if _RANK.search(prefix[-36:] + target_expression + tail[:32]):
        return DirectValueTypeDecision("RANK", "RECLASSIFY_TO_RANK")
    return DirectValueTypeDecision("DIRECT_VALUE", None)


def _target_clause(source: str, expression: str) -> tuple[str, int, int]:
    span = _find_target_span(source, expression)
    if span is None:
        return source, -1, 0
    start, end = span
    left = max(0, start - 80)
    right = min(len(source), end + 80)
    window = source[left:right]
    local_start = start - left
    for marker in ("반면", "한편", ";", "。"):
        boundary = window.rfind(marker, 0, local_start)
        if boundary >= 0:
            cut = boundary + len(marker)
            window = window[cut:]
            local_start -= cut
    for marker in ("반면", "한편", ";", "。"):
        boundary = window.find(marker, local_start + (end - start))
        if boundary >= 0:
            window = window[:boundary]
    return window, local_start, end - start


def _find_target_span(source: str, expression: str) -> tuple[int, int] | None:
    compact = [re.escape(character) for character in expression if not character.isspace()]
    if not compact:
        return None
    match = re.search(r"\s*".join(compact), source)
    return match.span() if match is not None else None
