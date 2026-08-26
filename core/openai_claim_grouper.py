"""OpenAI strict function contract for assigning numeric mentions to Claim groups."""

from __future__ import annotations

import json

from pydantic import ValidationError

from core.claim_group_output_contract import (
    ClaimGroupingOutputPayload,
    claim_grouping_json_schema,
)
from schemas.claim_group import ClaimGroupingPlan, NumericMention


EMIT_CLAIM_GROUPS_FUNCTION_NAME = "emit_claim_groups"
GROUPING_INSTRUCTIONS = (
    "Group only the supplied numeric mentions into independently verifiable Korean news claims. "
    "Never invent a mention or official value. A current value, its reference value, and its "
    "change belong to one group. A converted or parenthetical equivalent is not a new claim. "
    "Ranks, baselines, sample sizes, and explanatory numbers are CONTEXT_VALUE. Split groups "
    "only when indicators or populations are genuinely different. Use HUMAN_REVIEW when the "
    "relationship is ambiguous. Every supplied mention_id must appear exactly once."
    " READY requires at least one group, and every group main_mention_id must be assigned "
    "MAIN_VALUE or CHANGE_VALUE in that same group. CONTEXT_VALUE must have group_id null."
    " HUMAN_REVIEW requires groups=[]; assign every mention as CONTEXT_VALUE with group_id null."
)


def build_openai_grouping_request(
    source_sentence: str,
    mentions: list[NumericMention],
    model: str,
) -> dict[str, object]:
    return {
        "model": model,
        "instructions": GROUPING_INSTRUCTIONS,
        "input": json.dumps(
            {
                "source_sentence": source_sentence,
                "mentions": [mention.model_dump(mode="json") for mention in mentions],
            },
            ensure_ascii=False,
        ),
        "tools": [
            {
                "type": "function",
                "name": EMIT_CLAIM_GROUPS_FUNCTION_NAME,
                "description": "Assign every supplied numeric mention to a role and Claim group.",
                "parameters": claim_grouping_json_schema(),
                "strict": True,
            }
        ],
        "tool_choice": {
            "type": "function",
            "name": EMIT_CLAIM_GROUPS_FUNCTION_NAME,
        },
        "parallel_tool_calls": False,
    }


def parse_openai_grouping_response(payload: object) -> ClaimGroupingPlan:
    try:
        if not isinstance(payload, dict) or not isinstance(payload.get("output"), list):
            raise ValueError
        calls = [
            item
            for item in payload["output"]
            if isinstance(item, dict) and item.get("type") == "function_call"
        ]
        if len(calls) != 1 or calls[0].get("name") != EMIT_CLAIM_GROUPS_FUNCTION_NAME:
            raise ValueError
        arguments = calls[0].get("arguments")
        if not isinstance(arguments, str):
            raise ValueError
        provider_output = ClaimGroupingOutputPayload.model_validate_json(arguments)
    except (ValueError, TypeError, ValidationError):
        from core.openai_function_claim_extractor import OpenAIContractError

        raise OpenAIContractError("INVALID_CLAIM_GROUPING_OUTPUT") from None
    try:
        return provider_output.to_plan()
    except ValidationError:
        return ClaimGroupingPlan(
            status="HUMAN_REVIEW",
            reason="GROUPING_PROVIDER_CONTRADICTION",
            assignments=[],
            groups=[],
        )
