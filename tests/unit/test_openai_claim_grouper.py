import json

import pytest

from core.openai_claim_grouper import (
    EMIT_CLAIM_GROUPS_FUNCTION_NAME,
    build_openai_grouping_request,
    parse_openai_grouping_response,
)
from core.openai_function_claim_extractor import OpenAIContractError
from schemas.claim_group import NumericMention


def _mentions() -> list[NumericMention]:
    return [
        NumericMention(mention_id="n1", expression="60%", start=4, end=7),
        NumericMention(mention_id="n2", expression="58%", start=11, end=14),
    ]


def test_openai_group_request_forces_one_strict_group_function() -> None:
    request = build_openai_grouping_request("고용률은 60%로 전년 58%였다.", _mentions(), "gpt-test")

    assert request["tool_choice"] == {
        "type": "function",
        "name": EMIT_CLAIM_GROUPS_FUNCTION_NAME,
    }
    assert request["parallel_tool_calls"] is False
    assert request["tools"][0]["strict"] is True
    assert [item["mention_id"] for item in json.loads(request["input"])["mentions"]] == ["n1", "n2"]
    assert "READY requires at least one group" in request["instructions"]
    assert "HUMAN_REVIEW requires groups=[]" in request["instructions"]


def test_openai_group_response_is_validated_to_plan() -> None:
    payload = {
        "output": [
            {
                "type": "function_call",
                "name": EMIT_CLAIM_GROUPS_FUNCTION_NAME,
                "arguments": json.dumps(
                    {
                        "status": "READY",
                        "reason": "",
                        "assignments": [
                            {"mention_id": "n1", "role": "MAIN_VALUE", "group_id": "g1"},
                            {"mention_id": "n2", "role": "REFERENCE_VALUE", "group_id": "g1"},
                        ],
                        "groups": [
                            {"group_id": "g1", "main_mention_id": "n1", "indicator_hint": "고용률"}
                        ],
                    },
                    ensure_ascii=False,
                ),
            }
        ]
    }

    plan = parse_openai_grouping_response(payload)

    assert plan.status == "READY"
    assert plan.groups[0].main_mention_id == "n1"


def test_openai_group_response_accepts_ungrouped_context_value() -> None:
    payload = {
        "output": [{
            "type": "function_call",
            "name": EMIT_CLAIM_GROUPS_FUNCTION_NAME,
            "arguments": json.dumps({
                "status": "READY",
                "reason": "",
                "assignments": [
                    {"mention_id": "n1", "role": "CONTEXT_VALUE", "group_id": None},
                    {"mention_id": "n2", "role": "MAIN_VALUE", "group_id": "g1"},
                ],
                "groups": [{
                    "group_id": "g1",
                    "main_mention_id": "n2",
                    "indicator_hint": "고용률",
                }],
            }, ensure_ascii=False),
        }]
    }

    plan = parse_openai_grouping_response(payload)

    assert plan.assignments[0].role == "CONTEXT_VALUE"
    assert plan.assignments[0].group_id is None


def test_openai_group_response_rejects_free_text_or_unknown_role() -> None:
    with pytest.raises(OpenAIContractError):
        parse_openai_grouping_response({"output": [{"type": "message", "content": "free"}]})

    with pytest.raises(OpenAIContractError):
        parse_openai_grouping_response(
            {
                "output": [
                    {
                        "type": "function_call",
                        "name": EMIT_CLAIM_GROUPS_FUNCTION_NAME,
                        "arguments": json.dumps(
                            {
                                "status": "READY",
                                "reason": "",
                                "assignments": [
                                    {"mention_id": "n1", "role": "MADE_UP", "group_id": "g1"}
                                ],
                                "groups": [
                                    {"group_id": "g1", "main_mention_id": "n1", "indicator_hint": ""}
                                ],
                            }
                        ),
                    }
                ]
            }
        )


@pytest.mark.parametrize(
    "status,reason,assignments,groups",
    [
        (
            "READY",
            "",
            [
                {"mention_id": "n1", "role": "CONTEXT_VALUE", "group_id": None},
                {"mention_id": "n2", "role": "CONTEXT_VALUE", "group_id": None},
            ],
            [],
        ),
        (
            "HUMAN_REVIEW",
            "수치 관계가 모호함",
            [
                {"mention_id": "n1", "role": "CONTEXT_VALUE", "group_id": "g1"},
                {"mention_id": "n2", "role": "REFERENCE_VALUE", "group_id": "g1"},
            ],
            [
                {"group_id": "g1", "main_mention_id": "n1", "indicator_hint": "사망자 수"}
            ],
        ),
    ],
)
def test_openai_group_response_contradiction_fails_closed_to_human_review(
    status: str,
    reason: str,
    assignments: list[dict],
    groups: list[dict],
) -> None:
    payload = {
        "output": [{
            "type": "function_call",
            "name": EMIT_CLAIM_GROUPS_FUNCTION_NAME,
            "arguments": json.dumps({
                "status": status,
                "reason": reason,
                "assignments": assignments,
                "groups": groups,
            }, ensure_ascii=False),
        }]
    }

    plan = parse_openai_grouping_response(payload)
