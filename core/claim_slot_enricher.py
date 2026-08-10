"""Structured-output enrichment for the calculation-related ClaimSchema slots."""

from dataclasses import dataclass

from core.claim_parser import StructuredClaimExtractor, parse_claim
from core.deterministic_slot_enricher import infer_explicit_slots
from schemas.claim import ClaimSchema

_SUPPORTED_CALCULATIONS = {
    "DIRECT_VALUE",
    "DIFFERENCE",
    "GROWTH_RATE",
    "RATIO",
    "SHARE",
    "MULTIPLE",
    "RANK",
    "THRESHOLD",
}


@dataclass(frozen=True)
class SlotEnrichmentResult:
    """Claim update and its safe handoff state for catalog candidate search."""

    claim: ClaimSchema
    catalog_search_ready: bool
    reason_code: str | None


def enrich_claim_slots(
    claim: ClaimSchema, extractor: StructuredClaimExtractor
) -> SlotEnrichmentResult:
    """Fill only missing comparison/calculation/condition slots from strict output."""
    explicit = infer_explicit_slots(claim.source_sentence)
    if explicit.reason_code is not None:
        return _held(claim, explicit.reason_code)

    extracted = parse_claim(claim.source_sentence, extractor)
    if extracted.parse_status != "AUTO_OK":
        return _held(claim, "ENRICHMENT_PARSE_NOT_AUTO_OK")
    calculation = claim.calculation or explicit.calculation or extracted.calculation
    normalized_calculation = calculation.upper() if calculation else None
    enriched = claim.model_copy(
        update={
            "comparison": _non_empty_mapping(claim.comparison)
            or explicit.comparison
            or _non_empty_mapping(extracted.comparison),
            "calculation": normalized_calculation,
            "condition": _non_empty_mapping(claim.condition)
            or explicit.condition
            or _non_empty_mapping(extracted.condition),
        }
    )
    if normalized_calculation is None:
        return _held(enriched, "MISSING_CALCULATION")
    if normalized_calculation not in _SUPPORTED_CALCULATIONS:
        return _held(enriched, "UNSUPPORTED_CALCULATION")
    if normalized_calculation == "GROWTH_RATE" and not enriched.comparison:
        return _held(enriched, "MISSING_COMPARISON_FOR_GROWTH_RATE")
    return SlotEnrichmentResult(
        claim=enriched,
        catalog_search_ready=True,
        reason_code=None,
    )


def _non_empty_mapping(
    value: dict[str, str] | None,
) -> dict[str, str] | None:
    return value or None


def _held(claim: ClaimSchema, reason_code: str) -> SlotEnrichmentResult:
    return SlotEnrichmentResult(
        claim=claim.model_copy(
            update={"parse_status": "HOLD", "parse_reason": reason_code}
        ),
        catalog_search_ready=False,
        reason_code=reason_code,
    )
