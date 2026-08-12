"""Normalize the structured Claim dimension slot at the Registry boundary."""

from __future__ import annotations

import json
from collections.abc import Mapping


def normalized_dimension_members(dimension: Mapping[str, str] | None) -> dict[str, list[str]]:
    """Return named dimension members, unwrapping a JSON-encoded ``raw`` slot once."""
    if not dimension:
        return {}
    if set(dimension) == {"raw"}:
        raw = str(dimension["raw"]).strip()
        try:
            decoded = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return {"raw": [raw]} if raw else {}
        if isinstance(decoded, dict):
            return _normalize_mapping(decoded)
        if isinstance(decoded, list):
            values = _text_values(decoded)
            return {"raw": values} if values else {}
        return {"raw": [str(decoded)]} if decoded is not None else {}
    return _normalize_mapping(dimension)


def dimension_member_values(dimension: Mapping[str, str] | None) -> list[str]:
    """Flatten normalized dimension members in stable input order."""
    return [member for members in normalized_dimension_members(dimension).values() for member in members]


def _normalize_mapping(value: Mapping[object, object]) -> dict[str, list[str]]:
    normalized: dict[str, list[str]] = {}
    for key, members in value.items():
        texts = _text_values(members if isinstance(members, list) else [members])
        if texts:
            normalized[str(key)] = texts
    return normalized


def _text_values(values: list[object]) -> list[str]:
    return [text for value in values if (text := str(value).strip())]