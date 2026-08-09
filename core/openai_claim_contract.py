"""OpenAI Responses API contract for structured claim extraction."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from core.claim_output_contract import (
    CLAIM_OUTPUT_FIELD_NAMES,
    EMIT_CLAIM_FUNCTION_NAME,
    ClaimOutputPayload,
)
from schemas.claim import ClaimSchema


DUPLICATE_SLOT_KEY = "DUPLICATE_SLOT_KEY"


class SlotEntry(BaseModel):
    """One key-value entry used to encode map slots for strict tool schemas."""

    model_config = ConfigDict(extra="forbid", strict=True)

    key: str
    value: str


class OpenAIClaimToolPayload(BaseModel):
    """Strict OpenAI payload using entry arrays for semantic map slots."""

    model_config = ConfigDict(extra="forbid", strict=True)

    claim_id: str
    source_sentence: str
    indicator: str | None
    value: float | None
    unit: str | None
    time: str | None
    frequency: str | None
    region: str | None
    population: str | None
    dimension: list[SlotEntry] | None
    comparison: list[SlotEntry] | None
    calculation: str | None
    condition: list[SlotEntry] | None
    source_hint: str | None
    parse_status: Literal["AUTO_OK", "HOLD", "HUMAN_REVIEW"]
    parse_reason: str | None

    def to_claim(self) -> ClaimSchema:
        payload = self.model_dump()
        for slot_name in ("dimension", "comparison", "condition"):
            payload[slot_name] = _entries_to_mapping(slot_name, getattr(self, slot_name))
        return ClaimOutputPayload.model_validate(payload).to_claim()


def _entries_to_mapping(
    slot_name: str, entries: list[SlotEntry] | None
) -> dict[str, str] | None:
    if not entries:
        return None

    mapping: dict[str, str] = {}
    for entry in entries:
        if entry.key in mapping:
            raise ValueError(f"{DUPLICATE_SLOT_KEY}: {slot_name}.{entry.key}")
        mapping[entry.key] = entry.value
    return mapping


_NULLABLE_STRING: dict[str, Any] = {"type": ["string", "null"]}
_SLOT_ENTRY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "key": {"type": "string"},
        "value": {"type": "string"},
    },
    "required": ["key", "value"],
    "additionalProperties": False,
}
_NULLABLE_SLOT_ENTRIES: dict[str, Any] = {
    "type": ["array", "null"],
    "items": _SLOT_ENTRY_SCHEMA,
}

_OPENAI_CLAIM_PARAMETERS: dict[str, Any] = {
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
        "dimension": _NULLABLE_SLOT_ENTRIES,
        "comparison": _NULLABLE_SLOT_ENTRIES,
        "calculation": _NULLABLE_STRING,
        "condition": _NULLABLE_SLOT_ENTRIES,
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


def openai_emit_claim_tool_definition() -> dict[str, Any]:
    """Return the sole strict function tool accepted by the Responses API."""
    return {
        "type": "function",
        "name": EMIT_CLAIM_FUNCTION_NAME,
        "description": "Submit one parsed numerical news claim; this does not fetch or verify official values.",
        "strict": True,
        "parameters": deepcopy(_OPENAI_CLAIM_PARAMETERS),
    }
