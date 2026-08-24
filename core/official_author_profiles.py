"""Load and match reusable official-author evidence profiles."""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from pathlib import Path

from schemas.claim import ClaimSchema
from schemas.official_author import OfficialAuthorProfile


def load_official_author_profiles(path: Path) -> list[OfficialAuthorProfile]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("profiles") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        raise ValueError("OFFICIAL_AUTHOR_PROFILES_INVALID")
    return [OfficialAuthorProfile.model_validate(row) for row in rows]


def match_official_author_profile(
    claim: ClaimSchema, profiles: Sequence[OfficialAuthorProfile]
) -> OfficialAuthorProfile | None:
    """Return exactly one semantic profile; ambiguity fails closed."""
    fields = " ".join(
        str(value or "")
        for value in (
            claim.indicator,
            claim.population,
            claim.region,
            claim.dimension,
            claim.source_sentence,
        )
    )
    normalized = _normalize(fields)
    source_hint = _normalize(claim.source_hint or "")
    semantic_matches = [
        profile
        for profile in profiles
        if all(_normalize(term) in normalized for term in profile.indicator_terms)
    ]
    if len(semantic_matches) == 1:
        return semantic_matches[0]
    if not source_hint:
        return None
    hint_matches = [
        profile
        for profile in semantic_matches
        if profile.source_hint_terms
        and any(_normalize(term) in source_hint for term in profile.source_hint_terms)
    ]
    return hint_matches[0] if len(hint_matches) == 1 else None


def _normalize(value: str) -> str:
    return re.sub(r"[^0-9a-z가-힣]", "", value.casefold())
