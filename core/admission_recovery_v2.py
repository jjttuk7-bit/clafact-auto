"""Registry recovery with slot-contract revalidation for legacy AUTO_OK rows."""

from __future__ import annotations

import re
from typing import cast

from core.admission_recovery import (
    OfficialEvidenceResolver,
    RecoveryAction,
    RecoveryResult,
    recover_registry_record,
)
from core.claim_contract import assess_claim_contract
from core.claim_parser import StructuredClaimExtractor, parse_claim
from schemas.claim import ClaimSchema
from schemas.claim_registry import ClaimRegistryRecord


def recover_registry_record_v2(
    record: ClaimRegistryRecord,
    *,
    extractor: StructuredClaimExtractor,
    official_service: OfficialEvidenceResolver,
    article_context: str | None = None,
) -> RecoveryResult:
    """Revalidate legacy AUTO rows before delegating to the shared recovery engine."""
    if not _requires_slot_reparse(record.claim):
        return recover_registry_record(
            record,
            extractor=extractor,
            official_service=official_service,
            article_context=article_context,
        )
    reparsed = parse_claim(
        record.claim.source_sentence,
        extractor,
        article_published_at=record.article_published_at,
    )
    reparsed_record = record.model_copy(update={
        "claim": reparsed,
        "source_ref": "admission_recovery_v2",
        "slot_enrichment": {
            "stage": "SLOT_CONTRACT_REPARSE",
            "parent_claim_id": record.claim.claim_id,
            "source_ref": record.source_ref,
        },
    })
    recovered = recover_registry_record(
        reparsed_record,
        extractor=extractor,
        official_service=official_service,
        article_context=article_context,
    )
    return RecoveryResult(cast(RecoveryAction, "SLOT_REPARSE"), recovered.entries)


def _requires_slot_reparse(claim: ClaimSchema) -> bool:
    if claim.parse_status != "AUTO_OK":
        return False
    if assess_claim_contract(claim).status == "HOLD":
        return True
    source = claim.source_sentence
    indicator = (claim.indicator or "").replace(" ", "")
    if "쉬었음" in source and indicator in {"총인구", "인구"}:
        return True
    if claim.unit == "대" and claim.value is not None:
        age_token = re.search(r"(?<!\d)(\d{1,2})대", source)
        if age_token and float(age_token.group(1)) == float(claim.value):
            return True
    return False
