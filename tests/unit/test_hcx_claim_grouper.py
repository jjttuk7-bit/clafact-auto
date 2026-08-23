import json

import pytest

from core.hcx_claim_grouper import (
    build_hcx_grouping_request,
    parse_hcx_grouping_content,
)
from schemas.claim_group import NumericMention


def _mentions() -> list[NumericMention]:
    return [
        NumericMention(mention_id="n1", expression="60%", start=4, end=7),
        NumericMention(mention_id="n2", expression="58%", start=11, end=14),
    ]


def test_hcx_group_request_uses_json_schema_and_zero_temperature() -> None:
    request = build_hcx_grouping_request("고용률은 60%로 전년 58%였다.", _mentions())

    assert request["temperature"] == 0
    assert request["responseFormat"]["type"] == "json"
    assert request["responseFormat"]["schema"]["additionalProperties"] is False


def test_hcx_group_content_is_validated() -> None:
    plan = parse_hcx_grouping_content(
        json.dumps(
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
        )
    )

    assert plan.status == "READY"
    assert len(plan.groups) == 1


def test_hcx_group_content_rejects_unstructured_text() -> None:
    with pytest.raises(ValueError):
        parse_hcx_grouping_content("고용률 하나입니다")
