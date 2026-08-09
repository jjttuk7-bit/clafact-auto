from __future__ import annotations

import copy

import pytest
from pydantic import ValidationError

from core.claim_output_contract import claim_output_json_schema
from core.hcx_function_claim_extractor import (
    build_function_claim_request,
    parse_emit_claim_tool_call,
)


def _arguments() -> dict[str, object]:
    return {
        "claim_id": "claim-1",
        "source_sentence": "2025년 전국 고용률은 70%였다.",
        "indicator": "고용률",
        "value": 70.0,
        "unit": "%",
        "time": "2025년",
        "frequency": "년",
        "region": "전국",
        "population": None,
        "dimension": None,
        "comparison": None,
        "calculation": "DIRECT_VALUE",
        "condition": None,
        "source_hint": None,
        "parse_status": "AUTO_OK",
        "parse_reason": None,
    }


def _payload(arguments: object | None = None) -> dict[str, object]:
    return {
        "result": {
            "message": {
                "toolCalls": [
                    {
                        "id": "call-1",
                        "type": "function",
                        "function": {
                            "name": "emit_claim",
                            "arguments": _arguments() if arguments is None else arguments,
                        },
                    }
                ]
            },
            "finishReason": "tool_calls",
        }
    }


def test_function_request_forces_one_emit_claim_tool_without_other_hcx_modes() -> None:
    body = build_function_claim_request("2025년 전국 고용률은 70%였다.")

    assert [tool["function"]["name"] for tool in body["tools"]] == ["emit_claim"]
    assert body["tools"][0]["function"]["parameters"] == claim_output_json_schema()
    assert body["toolChoice"] == {
        "type": "function",
        "function": {"name": "emit_claim"},
    }
    assert "responseFormat" not in body
    assert "thinking" not in body


def test_valid_emit_claim_arguments_are_validated_as_claim_schema() -> None:
    claim = parse_emit_claim_tool_call(_payload())

    assert claim.indicator == "고용률"
    assert claim.dimension is None
    assert claim.parse_status == "AUTO_OK"


@pytest.mark.parametrize(
    ("mutate", "reason"),
    [
        (lambda payload: payload["result"]["message"].update(toolCalls=[]), "ONE_TOOL_CALL_REQUIRED"),
        (
            lambda payload: payload["result"]["message"]["toolCalls"].append(
                copy.deepcopy(payload["result"]["message"]["toolCalls"][0])
            ),
            "ONE_TOOL_CALL_REQUIRED",
        ),
        (
            lambda payload: payload["result"]["message"]["toolCalls"][0].update(type="other"),
            "EMIT_CLAIM_TOOL_REQUIRED",
        ),
        (
            lambda payload: payload["result"]["message"]["toolCalls"][0]["function"].update(name="fetch_kosis"),
            "EMIT_CLAIM_TOOL_REQUIRED",
        ),
        (
            lambda payload: payload["result"]["message"]["toolCalls"][0]["function"].update(arguments="{}"),
            "EMIT_CLAIM_ARGUMENTS_OBJECT_REQUIRED",
        ),
    ],
)
def test_invalid_tool_call_envelopes_are_rejected(mutate, reason: str) -> None:
    payload = _payload()
    mutate(payload)

    with pytest.raises(ValueError, match=reason):
        parse_emit_claim_tool_call(payload)


@pytest.mark.parametrize(
    "mutate_arguments",
    [
        lambda arguments: arguments.pop("condition"),
        lambda arguments: arguments.update(unexpected="not allowed"),
        lambda arguments: arguments.update(value="seventy"),
        lambda arguments: arguments.update(dimension={"age": 20}),
    ],
)
def test_invalid_claim_arguments_are_rejected_by_pydantic(mutate_arguments) -> None:
    arguments = _arguments()
    mutate_arguments(arguments)

    with pytest.raises(ValidationError):
        parse_emit_claim_tool_call(_payload(arguments))