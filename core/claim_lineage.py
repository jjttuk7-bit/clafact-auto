"""Preserve immutable parent Claims and every derived child Claim."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field


class ClaimLineageRecord(BaseModel):
    """One parent-to-child relationship created by Claim splitting."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    parent_claim_id: str = Field(min_length=1)
    child_claim_id: str = Field(min_length=1)
    child_ordinal: int = Field(ge=1)
    source_sentence: str = Field(min_length=1)
    target_expression: str = Field(min_length=1)


@dataclass(frozen=True, slots=True)
class ClaimLineageValidation:
    parent_count: int
    child_count: int
    missing_parent_ids: list[str]
    unexpected_parent_ids: list[str]
    duplicate_child_ids: list[str]
    duplicate_parent_ordinals: list[str]

    @property
    def is_valid(self) -> bool:
        return not any(
            (
                self.missing_parent_ids,
                self.unexpected_parent_ids,
                self.duplicate_child_ids,
                self.duplicate_parent_ordinals,
            )
        )


def validate_claim_lineage(
    records: list[ClaimLineageRecord],
    *,
    expected_parent_ids: set[str],
) -> ClaimLineageValidation:
    """Return deterministic coverage and uniqueness diagnostics."""

    observed_parent_ids = {record.parent_claim_id for record in records}
    child_counts = Counter(record.child_claim_id for record in records)
    ordinal_counts = Counter(
        (record.parent_claim_id, record.child_ordinal) for record in records
    )
    return ClaimLineageValidation(
        parent_count=len(observed_parent_ids),
        child_count=len(records),
        missing_parent_ids=sorted(expected_parent_ids - observed_parent_ids),
        unexpected_parent_ids=sorted(observed_parent_ids - expected_parent_ids),
        duplicate_child_ids=sorted(
            child_id for child_id, count in child_counts.items() if count > 1
        ),
        duplicate_parent_ordinals=sorted(
            f"{parent_id}:{ordinal}"
            for (parent_id, ordinal), count in ordinal_counts.items()
            if count > 1
        ),
    )

