from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from core.claim_output_contract import CLAIM_OUTPUT_FIELD_NAMES
from core.openai_claim_contract import (
    DUPLICATE_SLOT_KEY,
    OpenAIClaimToolPayload,
    openai_emit_claim_tool_definition,
)


def _payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "claim_id": "claim-1",
        "source_sentence": "지난해 취업자는 10만 명 늘었다.",
        "indicator": "취업자 수",
        "value": 100_000.0,
        "unit": "명",
        "time": "지난해",
        "frequency": "연간",
        "region": "전국",
        "population": "15세 이상",
        "dimension": [{"key": "성별", "value": "전체"}],
        "comparison": [{"key": "방식", "value": "전년 대비"}],
        "calculation": "증감",
        "condition": [{"key": "고용형태", "value": "전체"}],
        "source_hint": "통계청",
        "parse_status": "AUTO_OK",
        "parse_reason": None,
    }
    payload.update(overrides)
    return payload


def test_openai_tool_is_the_only_responses_api_function_tool() -> None:
    tool = openai_emit_claim_tool_definition()

    assert set(tool) == {"type", "name", "description", "strict", "parameters"}
    assert tool["type"] == "function"
    assert tool["name"] == "emit_claim"
    assert tool["strict"] is True


def test_openai_tool_requires_exactly_all_claim_output_fields() -> None:
    parameters = openai_emit_claim_tool_definition()["parameters"]

    assert parameters["additionalProperties"] is False
    assert set(parameters["required"]) == set(CLAIM_OUTPUT_FIELD_NAMES)
    assert len(parameters["required"]) == len(CLAIM_OUTPUT_FIELD_NAMES)


@pytest.mark.parametrize("slot_name", ["dimension", "comparison", "condition"])
def test_map_slot_entry_schema_is_closed_and_requires_key_value(slot_name: str) -> None:
    slot_schema = openai_emit_claim_tool_definition()["parameters"]["properties"][slot_name]
    entry_schema = slot_schema["items"]

    assert slot_schema["type"] == ["array", "null"]
    assert entry_schema["type"] == "object"
    assert entry_schema["additionalProperties"] is False
    assert set(entry_schema["required"]) == {"key", "value"}


def test_payload_converts_entry_arrays_to_internal_dict_slots() -> None:
    claim = OpenAIClaimToolPayload.model_validate(_payload()).to_claim()

    assert claim.dimension == {"성별": "전체"}
    assert claim.comparison == {"방식": "전년 대비"}
    assert claim.condition == {"고용형태": "전체"}


def test_payload_converts_empty_entry_arrays_to_none() -> None:
    claim = OpenAIClaimToolPayload.model_validate(
        _payload(dimension=[], comparison=[], condition=[])
    ).to_claim()

    assert claim.dimension is None
    assert claim.comparison is None
    assert claim.condition is None


def test_payload_accepts_nullable_scalar_fields() -> None:
    claim = OpenAIClaimToolPayload.model_validate(
        _payload(
            indicator=None,
            value=None,
            unit=None,
            time=None,
            frequency=None,
            region=None,
            population=None,
            calculation=None,
            source_hint=None,
            parse_reason=None,
        )
    ).to_claim()

    assert claim.indicator is None
    assert claim.value is None
    assert claim.source_hint is None


@pytest.mark.parametrize("slot_name", ["dimension", "comparison", "condition"])
def test_duplicate_map_slot_keys_are_rejected(slot_name: str) -> None:
    duplicate_entries = [
        {"key": "같은 키", "value": "첫 값"},
        {"key": "같은 키", "value": "둘째 값"},
    ]
    parsed = OpenAIClaimToolPayload.model_validate(_payload(**{slot_name: duplicate_entries}))

    with pytest.raises(ValueError, match=DUPLICATE_SLOT_KEY):
        parsed.to_claim()


def test_payload_rejects_unknown_top_level_keys() -> None:
    with pytest.raises(ValidationError):
        OpenAIClaimToolPayload.model_validate(_payload(unknown="not allowed"))


def test_payload_rejects_unknown_slot_entry_keys() -> None:
    with pytest.raises(ValidationError):
        OpenAIClaimToolPayload.model_validate(
            _payload(dimension=[{"key": "성별", "value": "전체", "unknown": "no"}])
        )
