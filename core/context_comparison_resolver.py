"""Resolve one explicit period-comparison basis from preceding article context."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class ContextComparison:
    comparison_type: str
    sentence_ids: tuple[str, ...]
    sentences: tuple[str, ...]


_BASIS_TERMS = {
    "YEAR_OVER_YEAR": (
        "전년 동월 대비",
        "전년 같은 달 대비",
        "전년 같은 달보다",
        "작년 같은 달 대비",
        "작년 같은 달보다",
        "전년 대비",
        "작년보다",
    ),
    "MONTH_OVER_MONTH": (
        "전월 대비",
        "전달 대비",
        "전월보다",
        "전달보다",
    ),
    "QUARTER_OVER_QUARTER": (
        "전분기 대비",
        "직전 분기 대비",
        "전분기보다",
    ),
}


def resolve_context_comparison(
    sentences: Sequence[tuple[str, str]],
) -> ContextComparison | None:
    """Return one basis only when every explicit context basis agrees."""
    evidence: dict[str, list[tuple[str, str]]] = {}
    for sentence_id, sentence in sentences:
        compact = " ".join(sentence.split())
        for comparison_type, terms in _BASIS_TERMS.items():
            if any(term in compact for term in terms):
                evidence.setdefault(comparison_type, []).append(
                    (sentence_id, sentence.strip())
                )
    if len(evidence) != 1:
        return None
    comparison_type, rows = next(iter(evidence.items()))
    return ContextComparison(
        comparison_type=comparison_type,
        sentence_ids=tuple(sentence_id for sentence_id, _ in rows),
        sentences=tuple(sentence for _, sentence in rows),
    )
