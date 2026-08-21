"""Deterministic splitting and structural multi-Claim detection."""

from __future__ import annotations

import re


_CLAUSE_SEPARATOR = re.compile(r"\s*(?:,(?!\d)|(?:였|었|이)고|그리고)\s*")
_NUMBER = re.compile(r"\d+(?:[,.]\d+)*(?:(?:만|억|천)\d+(?:[,.]\d+)*)*(?:%|%p|명|원|건|배|억|만|천|ha|대|㏊)?")
_CLAIM_VALUE = re.compile(r"\d+(?:[,.]\d+)*(?:(?:만|억|천)\d+(?:[,.]\d+)*)*(?:%p|%|명|원|건|배|억|만|천|ha|대|㏊)?")
_BASE_YEAR_ANNOTATION = re.compile(r"\(\s*(?:19|20)\d{2}년\s*=\s*\d+(?:[.]\d+)?\s*\)")
_HISTORICAL_REFERENCE = re.compile(r"(?:(?:작년|지난해|전년)\s*\d{1,2}월|(?:19|20)\d{2}년\s*\d{1,2}월)\s*\([^)]*\)\s*(?:이후|만에)")
_CHANGE_OR_COMPARISON = re.compile(
    r"전년|전월|전분기|동월|동기|1년 전|대비|보다|비해|늘(?:었|었|어|어난)|"
    r"줄(?:었|었|어|어든)|증가|감소|상승|하락|올랐|내렸|확대|축소"
)
_VALUE_UNIT = re.compile(r"(?:%p|%|명|원|건|배|억|만|천|ha|대|㏊)$")
_TIME_OR_RANGE_SUFFIX = re.compile(r"\s*(?:~|년|월|일|분기|개월|일간|주|차례|번째|부터|까지)")
_AGE_GROUP_SUFFIX = re.compile(r"\s*(?:취업자|인구|남성|여성|청년|고령|이상|미만)")
_CURRENT_VALUE_CHANGE_SPLIT = re.compile(
    r"^(?P<subject>.+?)\s+(?P<value>\d+(?:[,.]\d+)*(?:(?:만|억|천)\d+(?:[,.]\d+)*)*(?:%p|%|명|원|건|배|억|만|천|ha|대|㏊)?)"
    r"(?:으로|로)\s+(?P<change>(?:전년|작년|지난해|전월|전분기|동월|동기|1년 전).+)$"
)


_GROWTH_WIDTH_SPLIT = re.compile(
    r"(?P<subject>(?:작년|지난해|올해)\s+[^.]+?은)\s+(?P<value>\d+(?:[.]\d+)?%)\s+늘어\s+(?P<change>전년\([^)]*\)에\s+비해\s+증가\s+폭이\s+커졌다\.)"
)
_STREAK_SPLIT = re.compile(
    r"^(?P<subject>.+?)\s+(?:역시\s+)?(?P<first>전년\s+대비\s+\d+(?:[.]\d+)?%)\s+(?:오르면서|상승하면서)\s+(?P<second>\d+개월\s+연속\s+\d+(?:[.]\d+)?%\s+상승을\s+기록했다\.)$"
)
_TOTAL_AFTER_CHANGE_SPLIT = re.compile(
    r".*?(?P<subject>지난\s+\d{1,2}월\s+[^.]+?수는)\s+(?P<change>1년\s+전보다\s+\d+(?:[,.]\d+)*(?:만\d+)?명(?:\([^)]*%\))?\s+증가한)\s+(?P<total>\d+(?:만\d+)?명)이다\."
)

def detect_structural_multi_claim(sentence: str) -> bool:
    """Return whether a sentence contains at least two statistical value assertions."""
    normalized = _BASE_YEAR_ANNOTATION.sub("", sentence.strip())
    normalized = _HISTORICAL_REFERENCE.sub("", normalized)
    return (
        len(_statistical_values(normalized)) >= 2
        and bool(_CHANGE_OR_COMPARISON.search(normalized))
    )


def _statistical_values(sentence: str) -> list[str]:
    values: list[str] = []
    for match in _CLAIM_VALUE.finditer(sentence):
        token = match.group()
        suffix = sentence[match.end():]
        if _TIME_OR_RANGE_SUFFIX.match(suffix):
            continue
        if token.endswith("대") and _AGE_GROUP_SUFFIX.match(suffix):
            continue
        if _VALUE_UNIT.search(token) or "." in token or "," in token:
            values.append(token)
    return values


def _split_current_value_and_change(sentence: str) -> list[str] | None:
    match = _CURRENT_VALUE_CHANGE_SPLIT.match(sentence)
    if match is None:
        return None
    subject = match.group("subject").strip()
    value = match.group("value")
    change = match.group("change").strip()
    return [f"{subject} {value}이다.", f"{subject} {change}"]


def _split_remaining_multi_patterns(sentence: str) -> list[str] | None:
    growth = _GROWTH_WIDTH_SPLIT.search(sentence)
    if growth is not None:
        subject = growth.group("subject")
        return [f"{subject} {growth.group('value')} 늘었다.", f"{subject} {growth.group('change')}"]
    streak = _STREAK_SPLIT.match(sentence)
    if streak is not None:
        subject = streak.group("subject")
        return [f"{subject}는 {streak.group('first')} 올랐다.", f"{subject}는 {streak.group('second')}"]
    total = _TOTAL_AFTER_CHANGE_SPLIT.match(sentence)
    if total is not None:
        subject = total.group("subject")
        change = total.group("change").replace("증가한", "증가했다")
        return [f"{subject} {change}.", f"{subject} {total.group('total')}이다."]
    return None

def split_complex_claim(sentence: str) -> list[str]:
    """Split only numeric clauses; leave singular claims exactly intact."""
    normalized = sentence.strip()
    remaining_parts = _split_remaining_multi_patterns(normalized)
    if remaining_parts is not None:
        return remaining_parts
    structured_parts = _split_current_value_and_change(normalized)
    if structured_parts is not None:
        return structured_parts
    if len(_NUMBER.findall(normalized)) < 2:
        return [normalized]

    clauses = [clause.strip() for clause in _CLAUSE_SEPARATOR.split(normalized) if clause.strip()]
    if len(clauses) < 2 or not all(_NUMBER.search(clause) for clause in clauses):
        return [normalized]
    return clauses