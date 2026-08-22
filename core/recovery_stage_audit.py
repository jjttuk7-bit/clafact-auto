"""Build parent/child lineage and pre-official stage evidence for recovered Claims."""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256

from core.claim_lineage import ClaimLineageRecord
from schemas.claim import ClaimSchema
from schemas.stage_result import StageResultSchema


def build_recovery_stage_audit(
    *,
    parent_claim_id: str,
    claim: ClaimSchema,
    child_ordinal: int,
    recovery_action: str,
    admission_route: str,
    target_expression: str | None = None,
) -> tuple[ClaimLineageRecord, tuple[StageResultSchema, ...]]:
    """Describe what split/parse did without inventing official lookup evidence."""

    target_expression = target_expression or _target_expression(claim)
    lineage = ClaimLineageRecord(
        parent_claim_id=parent_claim_id,
        child_claim_id=claim.claim_id,
        child_ordinal=child_ordinal,
        source_sentence=claim.source_sentence,
        target_expression=target_expression,
    )
    now = datetime.now(timezone.utc).isoformat()
    input_hash = sha256(claim.source_sentence.encode("utf-8")).hexdigest()
    split_status = "PASS" if recovery_action == "MULTI_CLAIM_SPLIT" else "SKIPPED"
    split_reason = None if split_status == "PASS" else "SINGLE_CLAIM_OR_STORED_RESULT"
    parse_status = (
        "PASS" if admission_route == "KOSIS_PIPELINE_ELIGIBLE" else "HUMAN_REVIEW"
    )
    parse_reason = None if parse_status == "PASS" else (
        claim.parse_reason or admission_route
    )
    common = {
        "parent_claim_id": parent_claim_id,
        "child_claim_id": claim.claim_id,
        "input_hash": input_hash,
        "started_at": now,
        "finished_at": now,
        "code_version": "admission-recovery-v3",
        "data_version": "claim-schema-v1",
        "attempt": 1,
    }
    return lineage, (
        StageResultSchema(
            **common,
            stage="CLAIM_SPLIT",
            status=split_status,
            reason_code=split_reason,
            output_ref=claim.claim_id,
        ),
        StageResultSchema(
            **common,
            stage="CLAIM_PARSE",
            status=parse_status,
            reason_code=parse_reason,
            output_ref=claim.claim_id,
        ),
    )


def _target_expression(claim: ClaimSchema) -> str:
    if claim.value is not None:
        value = f"{claim.value:g}"
        return f"{value}{claim.unit or ''}"
    return claim.source_sentence
