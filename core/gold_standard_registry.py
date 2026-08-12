"""Validation contract for immutable 12-slot gold Claim Registry artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from core.claim_registry_loader import load_claim_registry

GOLD_SLOT_NAMES = (
    "indicator", "value", "unit", "time", "frequency", "region", "population",
    "dimension", "comparison", "calculation", "condition", "source_hint",
)


def validate_gold_standard_registry(path: Path, *, expected_count: int) -> dict[str, Any]:
    """Validate count, source/Claim identity, and allowed empty semantic slots."""
    loaded = load_claim_registry(path)
    records = loaded.records
    claim_ids = [record.claim.claim_id for record in records]
    return {
        "actual_count": len(records),
        "expected_count": expected_count,
        "count_matches": len(records) == expected_count,
        "load_error_count": len(loaded.errors),
        "claim_id_unique": len(claim_ids) == len(set(claim_ids)),
        "source_key_unique": len({(record.article_id, record.sentence_id) for record in records}) == len(records),
        "slot_non_null_counts": {
            slot: sum(getattr(record.claim, slot) is not None for record in records)
            for slot in GOLD_SLOT_NAMES
        },
        "slot_null_counts": {
            slot: sum(getattr(record.claim, slot) is None for record in records)
            for slot in GOLD_SLOT_NAMES
        },
        "source_refs": sorted({record.source_ref for record in records}),
    }
