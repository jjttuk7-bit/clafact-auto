"""Structured-output boundary for converting sentences to claim contracts."""

from __future__ import annotations

import re
from datetime import date
from hashlib import sha256
from typing import Protocol

from core.claim_contract import assess_claim_contract
from core.claim_time_resolver import resolve_relative_time
from core.deterministic_slot_enricher import apply_explicit_slots
from schemas.claim import ClaimSchema


class StructuredClaimExtractor(Protocol):
    """External interpretation adapter that must return a validated schema object."""

    def extract(
        self, source_sentence: str, *, article_published_at: date | None = None
    ) -> ClaimSchema:
        """Return only a Pydantic ClaimSchema, never an unstructured response."""


_AUTO_REQUIRED_SLOTS = ("indicator", "value", "unit", "time")


def parse_claim(
    source_sentence: str,
    extractor: StructuredClaimExtractor | None = None,
    *,
    article_published_at: date | None = None,
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

    extracted = (
        extractor.extract(normalized_source, article_published_at=article_published_at)
        if article_published_at is not None
        else extractor.extract(normalized_source)
    )
    if not isinstance(extracted, ClaimSchema):
        raise TypeError("Structured extractor must return ClaimSchema")

    claim = extracted.model_copy(
        update={"claim_id": claim_id, "source_sentence": normalized_source}
    )
    claim = _with_explicit_comparison(claim, normalized_source)
    if claim.parse_status != "AUTO_OK":
        return claim
    claim = _with_standard_unit(claim)
    claim = _with_explicit_decrease_sign(claim, normalized_source)
    claim = _with_standard_month(claim)
    claim = resolve_relative_time(claim, article_published_at)
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
    claim = apply_explicit_slots(claim)
    decision = assess_claim_contract(claim)
    if decision.status == "HOLD":
        return claim.model_copy(update={
            "parse_status": "HOLD",
            "parse_reason": decision.reason_code,
        })
    return claim


def _claim_id(source_sentence: str) -> str:
    digest = sha256(source_sentence.encode("utf-8")).hexdigest()[:16]
    return f"claim_{digest}"


def _with_standard_unit(claim: ClaimSchema) -> ClaimSchema:
    """Normalize common provider aliases to the engine's canonical unit symbols."""
    if claim.unit is None:
        return claim
    normalized_unit = claim.unit.strip().casefold()
    if normalized_unit not in {"percent", "percentage", "퍼센트"}:
        return claim
    return claim.model_copy(update={"unit": "%"})


def _with_standard_month(claim: ClaimSchema) -> ClaimSchema:
    """Normalize an unambiguous ISO month to the canonical Korean month label."""
    if claim.time is None:
        return claim
    match = re.fullmatch(r"(?P<year>\d{4})-(?P<month>0[1-9]|1[0-2])", claim.time.strip())
    if match is None:
        return claim
    return claim.model_copy(update={"time": f"{match['year']}년 {int(match['month'])}월"})


def _with_explicit_decrease_sign(claim: ClaimSchema, source_sentence: str) -> ClaimSchema:
    """Preserve the signed meaning of an explicit percentage decrease in source text."""
    if (
        claim.value is None
        or claim.value < 0
        or (claim.unit or "").strip() != "%"
        or not any(marker in source_sentence for marker in ("하락", "감소"))
    ):
        return claim
    return claim.model_copy(update={"value": -abs(claim.value)})


def _with_explicit_comparison(claim: ClaimSchema, source_sentence: str) -> ClaimSchema:
    """Backfill only comparison language explicitly present in the source."""
    if claim.comparison is not None:
        return claim
    compact_source = "".join(source_sentence.split())
    if re.search(r"전체.+의\s*[-+]?\d+(?:\.\d+)?\s*%", source_sentence):
        return claim.model_copy(update={"comparison": {"type": "SHARE_OF_TOTAL"}})
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
