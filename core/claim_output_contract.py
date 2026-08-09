"""Canonical JSON contracts for structured numerical claim extraction."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


SEMANTIC_SLOT_NAMES = (
    "indicator",
    "value",
    "unit",
    "time",
    "frequency",
    "region",
    "population",
    "dimension",
    "comparison",
    "calculation",
    "condition",
    "source_hint",
)

CLAIM_OUTPUT_FIELD_NAMES = (
    "claim_id",
    "source_sentence",
    *SEMANTIC_SLOT_NAMES,
    "parse_status",
    "parse_reason",
)

_NULLABLE_STRING: dict[str, Any] = {"type": ["string", "null"]}
_NULLABLE_STRING_MAP: dict[str, Any] = {
    "type": ["object", "null"],
    "additionalProperties": {"type": "string"},
}

_CLAIM_OUTPUT_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "claim_id": {"type": "string"},
        "source_sentence": {"type": "string"},
        "indicator": _NULLABLE_STRING,
        "value": {"type": ["number", "null"]},
        "unit": _NULLABLE_STRING,
        "time": _NULLABLE_STRING,
        "frequency": _NULLABLE_STRING,
        "region": _NULLABLE_STRING,
        "population": _NULLABLE_STRING,
        "dimension": _NULLABLE_STRING_MAP,
        "comparison": _NULLABLE_STRING_MAP,
        "calculation": _NULLABLE_STRING,
        "condition": _NULLABLE_STRING_MAP,
        "source_hint": _NULLABLE_STRING,
        "parse_status": {
            "type": "string",
            "enum": ["AUTO_OK", "HOLD", "HUMAN_REVIEW"],
        },
        "parse_reason": _NULLABLE_STRING,
    },
    "required": list(CLAIM_OUTPUT_FIELD_NAMES),
    "additionalProperties": False,
}


def claim_output_json_schema() -> dict[str, Any]:
    """Return an isolated copy of the provider-neutral Claim JSON Schema."""
    return deepcopy(_CLAIM_OUTPUT_JSON_SCHEMA)
