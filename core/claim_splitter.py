"""Deterministic splitting and structural multi-Claim detection."""

from __future__ import annotations

import re


_CLAUSE_SEPARATOR = re.compile(r"\s*(?:,(?!\d)|(?:였|었|이)고|그리고)\s*")
_NUMBER = re.compile(r"\d+(?:[,.]\d+)*(?:%|%p|명|원|건|배|억|만|천|ha|대|㏊)?")
_BASE_YEAR_ANNOTATION = re.compile(r"\(\s*(?:19|20)\d{2}년\s*=\s*\d+(?:[.]\d+)?\s*\)")
_CHANGE_OR_COMPARISON = re.compile(
    r"전년|작년|지난해|전월|전분기|동월|동기|1년 전|대비|보다|늘(?:었|었|어|어난)|"
    r"줄(?:었|었|어|어든)|증가|감소|상승|하락|올랐|내렸|확대|축소"
)


def detect_structural_multi_claim(sentence: str) -> bool:
    """Return whether a sentence asserts a current value and a separate change Claim.

    A base-year annotation such as ``(2020년=100)`` is metadata for one value, not
    a second Claim.  In contrast, a present value and a year-over-year change are
    distinct verification targets under the approved Gold Set policy.
    """
    normalized = _BASE_YEAR_ANNOTATION.sub("", sentence.strip())
    return (
        len(_NUMBER.findall(normalized)) >= 2
        and bool(_CHANGE_OR_COMPARISON.search(normalized))
    )


def split_complex_claim(sentence: str) -> list[str]:
    """Split only numeric clauses; leave singular claims exactly intact."""
    normalized = sentence.strip()
    if len(_NUMBER.findall(normalized)) < 2:
        return [normalized]

    clauses = [clause.strip() for clause in _CLAUSE_SEPARATOR.split(normalized) if clause.strip()]
    if len(clauses) < 2 or not all(_NUMBER.search(clause) for clause in clauses):
        return [normalized]
    return clauses