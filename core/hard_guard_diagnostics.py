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
    rejected: Counter[str] = Counter()
    passed = 0
    for candidate in materialized:
        result = apply_hard_guard(claim, candidate)
        if result.passed:
            passed += 1
        for code in set(result.reject_codes):
            rejected[code] += 1
    return {
        "hard_guard_candidate_count": len(materialized),
        "hard_guard_passed_count": passed,
        **{
            f"hard_guard_reject_{code}": count
            for code, count in sorted(rejected.items())
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
