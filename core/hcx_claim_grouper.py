"""HCX Structured Output contract for assigning numeric mentions to Claim groups."""

from __future__ import annotations

import json

from core.claim_group_output_contract import (
    ClaimGroupingOutputPayload,
    claim_grouping_json_schema,
)
from core.openai_claim_grouper import GROUPING_INSTRUCTIONS
from schemas.claim_group import ClaimGroupingPlan, NumericMention


def build_hcx_grouping_request(
    source_sentence: str,
    mentions: list[NumericMention],
) -> dict[str, object]:
    return {
        "messages": [
            {"role": "system", "content": GROUPING_INSTRUCTIONS},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "source_sentence": source_sentence,
                        "mentions": [
                            mention.model_dump(mode="json") for mention in mentions
                        ],
                    },
                    ensure_ascii=False,
                ),
            },
        ],
        "temperature": 0,
        "maxCompletionTokens": 1024,
        "thinking": {"effort": "none"},
        "responseFormat": {
            "type": "json",
            "schema": claim_grouping_json_schema(),
        },
    }


def parse_hcx_grouping_content(content: str) -> ClaimGroupingPlan:
    normalized = (
        content.strip()
        .removeprefix("```json")
        .removeprefix("```")
        .removesuffix("```")
        .strip()
    )
    return ClaimGroupingOutputPayload.model_validate_json(normalized).to_plan()
