"""Build official-verification Registry rows from admitted multi-Claim children."""

from __future__ import annotations

from typing import Any

from schemas.claim import ClaimSchema
from schemas.claim_registry import ClaimRegistryRecord


def build_eligible_child_registry(
    parent_records: list[ClaimRegistryRecord],
    group_results: list[dict[str, Any]],
) -> list[ClaimRegistryRecord]:
    """Select only admitted children and preserve their immutable parent provenance."""

    parent_by_claim_id = _parents_by_claim_id(parent_records)
    records: list[ClaimRegistryRecord] = []
    seen_child_ids: set[str] = set()
    for result in group_results:
        parent_claim_id = str(result.get("claim_id") or "")
        eligible_children = [
            child
            for child in result.get("children") or []
            if isinstance(child, dict)
            and child.get("admission_route") == "KOSIS_PIPELINE_ELIGIBLE"
        ]
        if not eligible_children:
            continue
        parent = parent_by_claim_id.get(parent_claim_id)
        if parent is None:
            raise ValueError(f"PARENT_REGISTRY_RECORD_NOT_FOUND:{parent_claim_id}")
        if parent.article_published_at is None:
            raise ValueError(f"ARTICLE_DATE_REQUIRED:{parent_claim_id}")

        for ordinal, child in enumerate(eligible_children, start=1):
            claim = ClaimSchema.model_validate(child.get("claim"))
            if claim.claim_id in seen_child_ids:
                raise ValueError(
                    f"DUPLICATE_ELIGIBLE_CHILD_CLAIM_ID:{claim.claim_id}"
                )
            if claim.source_sentence != parent.claim.source_sentence:
                raise ValueError(f"CHILD_SOURCE_IDENTITY_MISMATCH:{claim.claim_id}")
            seen_child_ids.add(claim.claim_id)
            recovery_audit = child.get("recovery_audit")
            slot_enrichment = (
                dict(recovery_audit) if isinstance(recovery_audit, dict) else None
            )
            source_metadata = dict(parent.source_metadata)
            source_metadata.update(
                {
                    "parent_claim_id": parent_claim_id,
                    "grouping_source": "multi_claim_employment_20_final",
                }
            )
            records.append(
                parent.model_copy(
                    update={
                        "sentence_id": f"{parent.sentence_id}:multi:{ordinal}",
                        "source_ref": "multi_claim_official_input_v1",
                        "source_metadata": source_metadata,
                        "claim": claim,
                        "slot_enrichment": slot_enrichment,
                    }
                )
            )
    return records


def _parents_by_claim_id(
    records: list[ClaimRegistryRecord],
) -> dict[str, ClaimRegistryRecord]:
    parents: dict[str, ClaimRegistryRecord] = {}
    for record in records:
        claim_id = record.claim.claim_id
        if claim_id in parents:
            raise ValueError(f"DUPLICATE_PARENT_CLAIM_ID:{claim_id}")
        parents[claim_id] = record
    return parents
