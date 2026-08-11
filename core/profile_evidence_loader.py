"""Strict loading for profile evidence backed by immutable official snapshots."""

import json
from pathlib import Path

from pydantic import ValidationError

from schemas.profile_evidence import ProfileEvidenceSchema


def load_profile_evidence(path: Path) -> list[ProfileEvidenceSchema]:
    """Load a versioned evidence document and reject missing coordinate proof."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("profile_evidence_schema_version") != "v1":
        raise ValueError("Unsupported or missing profile_evidence_schema_version")
    rows = payload.get("evidence")
    if not isinstance(rows, list):
        raise ValueError("Profile evidence document requires an evidence list")
    try:
        evidence = [ProfileEvidenceSchema.model_validate(row) for row in rows]
    except ValidationError as error:
        raise ValueError(str(error)) from error
    profile_ids = [row.profile_id for row in evidence]
    if len(profile_ids) != len(set(profile_ids)):
        raise ValueError("Duplicate profile evidence ID")
    return evidence
