"""Select a KOSIS table only when official metadata proves one exact cell."""

from __future__ import annotations

from collections.abc import Iterable

from core.catalog_binding import apply_catalog_binding
from core.evidence_resolver_impl import resolve_evidence_cell
from core.hard_guard import apply_hard_guard
from schemas.candidate import KosisCandidateSchema
from schemas.claim import ClaimSchema
from schemas.concept import StandardConceptSchema


STRUCTURAL_RULE_ID = "OFFICIAL_STRUCTURAL_COORDINATE_RULE"


def select_official_candidate(
    claim: ClaimSchema,
    concept: StandardConceptSchema,
    candidates: Iterable[KosisCandidateSchema],
) -> list[KosisCandidateSchema]:
    """Apply bindings, then select one uniquely proven metadata coordinate."""
    bound = apply_catalog_binding(claim, concept, list(candidates))
    if (
        len(bound) == 1
        and bound[0].source_stat_id == "OFFICIAL_RECURRING_DOMAIN_BINDING"
    ):
        return bound

    confirmed: list[KosisCandidateSchema] = []
    for candidate in bound:
        if not apply_hard_guard(claim, candidate).passed:
            continue
        try:
            evidence = resolve_evidence_cell(claim, candidate)
        except (TypeError, ValueError):
            continue
        if evidence.status == "CONFIRMED":
            confirmed.append(candidate)
    if len(confirmed) != 1:
        return bound
    return [confirmed[0].model_copy(update={"source_stat_id": STRUCTURAL_RULE_ID})]
