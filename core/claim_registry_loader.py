"""Auditable JSONL loading for Claim Registry records."""

from dataclasses import dataclass
import json
from pathlib import Path

from pydantic import ValidationError

from schemas.claim_registry import ClaimRegistryRecord


@dataclass(frozen=True)
class ClaimRegistryLoadError:
    """One rejected Registry source row, retained for a safe review route."""

    line_number: int
    reason_code: str


@dataclass(frozen=True)
class ClaimRegistryLoadResult:
    """Typed records and row-level errors from one immutable JSONL source."""

    records: list[ClaimRegistryRecord]
    errors: list[ClaimRegistryLoadError]


def load_claim_registry(path: Path) -> ClaimRegistryLoadResult:
    """Load JSONL without silently dropping malformed or duplicate source rows."""
    records: list[ClaimRegistryRecord] = []
    errors: list[ClaimRegistryLoadError] = []
    seen_keys: set[tuple[str, str]] = set()
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            errors.append(ClaimRegistryLoadError(line_number, "INVALID_JSON"))
            continue
        try:
            record = ClaimRegistryRecord.model_validate(payload)
        except ValidationError:
            errors.append(ClaimRegistryLoadError(line_number, "INVALID_REGISTRY_RECORD"))
            continue
        source_key = (record.article_id, record.sentence_id)
        if source_key in seen_keys:
            errors.append(ClaimRegistryLoadError(line_number, "DUPLICATE_SOURCE_KEY"))
            continue
        seen_keys.add(source_key)
        records.append(record)
    return ClaimRegistryLoadResult(records=records, errors=errors)
