"""Strict JSON loading for versioned verification profiles."""

import json
from pathlib import Path

from schemas.verification_profile import VerificationProfileSchema


def load_verification_profiles(path: Path) -> list[VerificationProfileSchema]:
    """Load a versioned profile document and reject invalid or duplicate profiles."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("profile_schema_version") != "v1":
        raise ValueError("Unsupported or missing profile_schema_version")
    rows = payload.get("profiles")
    if not isinstance(rows, list):
        raise ValueError("Verification profile document requires a profiles list")
    profiles = [VerificationProfileSchema.model_validate(row) for row in rows]
    identifiers = [profile.profile_id for profile in profiles]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("Duplicate verification profile ID")
    return profiles
