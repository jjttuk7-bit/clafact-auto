"""Structured-output boundary for converting sentences to claim contracts."""

from __future__ import annotations

from hashlib import sha256
from typing import Protocol

from schemas.claim import ClaimSchema


class StructuredClaimExtractor(Protocol):
    """External interpretation adapter that must return a validated schema object."""

    def extract(self, source_sentence: str) -> ClaimSchema:
        """Return only a Pydantic ClaimSchema, never an unstructured response."""


_AUTO_REQUIRED_SLOTS = ("indicator", "value", "unit", "time")


def parse_claim(
    source_sentence: str, extractor: StructuredClaimExtractor | None = None
) -> ClaimSchema:
    """Parse a sentence using structured output and conservatively route uncertainty."""
    normalized_source = source_sentence.strip()
    if not normalized_source:
        raise ValueError("source_sentence must not be blank")

    claim_id = _claim_id(normalized_source)
    if extractor is None:
        return ClaimSchema(
            claim_id=claim_id,
            source_sentence=normalized_source,
            parse_status="HOLD",
            parse_reason="STRUCTURED_EXTRACTOR_NOT_CONFIGURED",
        )

    extracted = extractor.extract(normalized_source)
    if not isinstance(extracted, ClaimSchema):
        raise TypeError("Structured extractor must return ClaimSchema")

    claim = extracted.model_copy(
        update={"claim_id": claim_id, "source_sentence": normalized_source}
    )
    claim = _with_explicit_comparison(claim, normalized_source)
    if claim.parse_status != "AUTO_OK":
        return claim

    missing_slots = [slot for slot in _AUTO_REQUIRED_SLOTS if getattr(claim, slot) is None]
    if missing_slots:
        return claim.model_copy(
            update={
                "parse_status": "HOLD",
                "parse_reason": f"MISSING_REQUIRED_SLOTS:{','.join(missing_slots)}",
            }
        )
    return claim


def _claim_id(source_sentence: str) -> str:
    digest = sha256(source_sentence.encode("utf-8")).hexdigest()[:16]
    return f"claim_{digest}"


def _with_explicit_comparison(claim: ClaimSchema, source_sentence: str) -> ClaimSchema:
    """Backfill only comparison language explicitly present in the source."""
    if claim.comparison is not None:
        return claim
    compact_source = "".join(source_sentence.split())
    if "전년동월대비" not in compact_source:
        return claim
    return claim.model_copy(
        update={
            "comparison": {
                "type": "YEAR_OVER_YEAR",
                "reference_period": "전년 동월",
            }
        }
    )
