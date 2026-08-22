"""Freeze Registry inputs into a stable, auditable baseline."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from schemas.claim_registry import ClaimRegistryRecord


class BaselineRecordSchema(BaseModel):
    """Immutable identity and source fields for one Registry input row."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_index: int = Field(ge=1)
    parent_claim_id: str = Field(min_length=1)
    article_id: str = Field(min_length=1)
    sentence_id: str = Field(min_length=1)
    original_claim_id: str = Field(min_length=1)
    source_ref: str = Field(min_length=1)
    source_sentence: str = Field(min_length=1)
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class BaselineValidation:
    record_count: int
    unique_parent_count: int
    expected_count: int
    duplicate_parent_ids: list[str]
    missing_source_sentence_ids: list[str]

    @property
    def is_valid(self) -> bool:
        return (
            self.record_count == self.expected_count
            and self.unique_parent_count == self.expected_count
            and not self.duplicate_parent_ids
            and not self.missing_source_sentence_ids
        )


def build_baseline(records: list[ClaimRegistryRecord]) -> list[BaselineRecordSchema]:
    """Build stable identities without changing source Registry records."""

    baseline: list[BaselineRecordSchema] = []
    for source_index, record in enumerate(records, start=1):
        canonical_source = json.dumps(
            record.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        source_hash = sha256(canonical_source.encode("utf-8")).hexdigest()
        identity_source = "\0".join(
            (
                record.article_id,
                record.sentence_id,
                record.claim.claim_id,
                record.source_ref,
            )
        )
        parent_claim_id = "REG-" + sha256(
            identity_source.encode("utf-8")
        ).hexdigest()[:20]
        baseline.append(
            BaselineRecordSchema(
                source_index=source_index,
                parent_claim_id=parent_claim_id,
                article_id=record.article_id,
                sentence_id=record.sentence_id,
                original_claim_id=record.claim.claim_id,
                source_ref=record.source_ref,
                source_sentence=record.claim.source_sentence,
                source_sha256=source_hash,
            )
        )
    return baseline


def validate_baseline(
    records: list[BaselineRecordSchema], *, expected_count: int
) -> BaselineValidation:
    parent_counts = Counter(record.parent_claim_id for record in records)
    return BaselineValidation(
        record_count=len(records),
        unique_parent_count=len(parent_counts),
        expected_count=expected_count,
        duplicate_parent_ids=sorted(
            parent_id for parent_id, count in parent_counts.items() if count > 1
        ),
        missing_source_sentence_ids=sorted(
            record.parent_claim_id
            for record in records
            if not record.source_sentence.strip()
        ),
    )


def write_baseline(path: Path, records: list[BaselineRecordSchema]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(record.model_dump_json() + "\n" for record in records),
        encoding="utf-8",
    )

