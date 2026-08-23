"""Fail-closed recovery results for unresolved numeric Claim grouping."""

from __future__ import annotations

from typing import cast

from core.admission_recovery import RecoveryAction, RecoveryEntry, RecoveryResult
from schemas.claim_group import NumericMention
from schemas.claim_registry import ClaimRegistryRecord


def build_grouping_hold(
    record: ClaimRegistryRecord,
    *,
    mentions: list[NumericMention],
    reason_code: str,
) -> RecoveryResult:
    claim = record.claim.model_copy(
        update={"parse_status": "HOLD", "parse_reason": reason_code}
    )
    derived = record.model_copy(
        update={
            "claim": claim,
            "source_ref": "admission_recovery_v3",
            "slot_enrichment": {
                "stage": "ROLE_GROUPED_MULTI_CLAIM_SPLIT",
                "parent_claim_id": record.claim.claim_id,
                "numeric_mentions": [
                    mention.model_dump(mode="json") for mention in mentions
                ],
                "grouping_reason": reason_code,
                "admission_route": "STRUCTURAL_HOLD",
                "source_ref": record.source_ref,
            },
        }
    )
    entry = RecoveryEntry(
        record.claim.claim_id,
        derived,
        "STRUCTURAL_HOLD",
        None,
    )
    return RecoveryResult(cast(RecoveryAction, "MULTI_CLAIM_SPLIT"), [entry])
