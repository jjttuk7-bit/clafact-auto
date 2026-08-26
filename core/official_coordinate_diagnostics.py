"""Explain the exact official-coordinate boundary without changing selection."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Iterable

from core.evidence_resolver_impl import resolve_evidence_cell
from core.hard_guard import apply_hard_guard
from schemas.candidate import KosisCandidateSchema
from schemas.claim import ClaimSchema


@dataclass(frozen=True, slots=True)
class OfficialCoordinateDiagnostic:
    failure_boundary: str
    candidate_count: int
    hard_guard_pass_count: int
    confirmed_coordinate_count: int
    hard_guard_reject_counts: dict[str, int]
    unresolved_table_ids: tuple[str, ...]
    confirmed_table_ids: tuple[str, ...]


def diagnose_official_coordinates(
    claim: ClaimSchema,
    candidates: Iterable[KosisCandidateSchema],
) -> OfficialCoordinateDiagnostic:
    """Replay only deterministic Hard Guard and Evidence resolution decisions."""

    materialized = list(candidates)
    reject_codes: Counter[str] = Counter()
    hard_pass: list[KosisCandidateSchema] = []
    for candidate in materialized:
        guard = apply_hard_guard(claim, candidate)
        if guard.passed:
            hard_pass.append(candidate)
        else:
            reject_codes.update(guard.reject_codes)

    confirmed: list[str] = []
    unresolved: list[str] = []
    for candidate in hard_pass:
        try:
            evidence = resolve_evidence_cell(claim, candidate)
        except (TypeError, ValueError):
            unresolved.append(candidate.tbl_id)
            continue
        if evidence.status == "CONFIRMED":
            confirmed.append(candidate.tbl_id)
        else:
            unresolved.append(candidate.tbl_id)

    if not materialized:
        boundary = "CATALOG_NO_CANDIDATE"
    elif not hard_pass:
        boundary = "HARD_GUARD_REJECTED"
    elif not confirmed:
        boundary = "EVIDENCE_COORDINATE_UNRESOLVED"
    elif len(confirmed) > 1:
        boundary = "EVIDENCE_COORDINATE_AMBIGUOUS"
    else:
        boundary = "COORDINATE_CONFIRMED"
    return OfficialCoordinateDiagnostic(
        failure_boundary=boundary,
        candidate_count=len(materialized),
        hard_guard_pass_count=len(hard_pass),
        confirmed_coordinate_count=len(confirmed),
        hard_guard_reject_counts=dict(sorted(reject_codes.items())),
        unresolved_table_ids=tuple(unresolved),
        confirmed_table_ids=tuple(confirmed),
    )


__all__ = ["OfficialCoordinateDiagnostic", "diagnose_official_coordinates"]
