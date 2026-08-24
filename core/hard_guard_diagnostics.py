"""Auditable aggregate reasons for official candidates rejected by Hard Guard."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable

from core.hard_guard import apply_hard_guard
from schemas.candidate import KosisCandidateSchema
from schemas.claim import ClaimSchema


def summarize_hard_guard_rejections(
    claim: ClaimSchema,
    candidates: Iterable[KosisCandidateSchema],
) -> dict[str, int]:
    """Count candidate passes and stable reject codes without changing selection."""
    materialized = list(candidates)
    results = [apply_hard_guard(claim, candidate) for candidate in materialized]
    rejected: Counter[str] = Counter(
        code
        for result in results
        for code in set(result.reject_codes)
    )
    passed = sum(result.passed for result in results)
    reject_sizes = [len(set(result.reject_codes)) for result in results]
    minimum = min(reject_sizes, default=0)
    best_results = [
        result
        for result, size in zip(results, reject_sizes, strict=True)
        if size == minimum
    ]
    best_rejected: Counter[str] = Counter(
        code
        for result in best_results
        for code in set(result.reject_codes)
    )
    return {
        "hard_guard_candidate_count": len(materialized),
        "hard_guard_passed_count": passed,
        "hard_guard_best_candidate_count": len(best_results),
        "hard_guard_min_reject_count": minimum,
        **{
            f"hard_guard_reject_{code}": count
            for code, count in sorted(rejected.items())
        },
        **{
            f"hard_guard_best_reject_{code}": count
            for code, count in sorted(best_rejected.items())
        },
    }


def format_hard_guard_rejections(diagnostics: dict[str, object]) -> str:
    """Render only positive reject counters in a stable audit format."""
    prefix = "hard_guard_reject_"
    values = [
        f"{key.removeprefix(prefix)}:{int(value)}"
        for key, value in sorted(diagnostics.items())
        if key.startswith(prefix)
        and isinstance(value, (int, float))
        and int(value) > 0
    ]
    return " | ".join(values)
