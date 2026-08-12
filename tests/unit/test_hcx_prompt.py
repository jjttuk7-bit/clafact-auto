import json
from datetime import date

import pytest
from pydantic import ValidationError

from core.claim_output_contract import CLAIM_OUTPUT_FIELD_NAMES, claim_output_json_schema
from core.hcx_claim_extractor import (
    SYSTEM_PROMPT,
    build_structured_claim_request,
    parse_structured_claim_content,
)


def test_structured_prompt_marks_year_on_year_as_growth_rate() -> None:
    assert "GROWTH_RATE" in SYSTEM_PROMPT
    assert "same-month-last-year" in SYSTEM_PROMPT


def test_structured_prompt_routes_multiple_independent_values_to_review() -> None:
    assert "HUMAN_REVIEW" in SYSTEM_PROMPT
    assert "independent" in SYSTEM_PROMPT


def test_structured_prompt_requires_negative_sign_for_explicit_decrease() -> None:
    assert "negative" in SYSTEM_PROMPT
    assert "decrease" in SYSTEM_PROMPT


def test_structured_request_uses_complete_shared_claim_schema_only() -> None:
    body = build_structured_claim_request("2025년 고용률은 70%였다.")

    assert body["responseFormat"]["schema"] == claim_output_json_schema()
    assert body["responseFormat"]["schema"]["required"] == list(CLAIM_OUTPUT_FIELD_NAMES)
    assert "tools" not in body
    assert "toolChoice" not in body


def _complete_claim_payload() -> dict[str, object]:
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


def test_structured_response_requires_all_claim_contract_keys() -> None:
    payload = _complete_claim_payload()
    payload.pop("dimension")

    with pytest.raises(ValidationError):
        parse_structured_claim_content(json.dumps(payload))


def test_structured_response_accepts_explicit_nulls_for_optional_slots() -> None:
    claim = parse_structured_claim_content(json.dumps(_complete_claim_payload()))

    assert claim.dimension is None
    assert claim.condition is None

def test_structured_request_includes_article_date_context() -> None:
    body = build_structured_claim_request(
        "지난달 고용률은 70%였다.", article_published_at=date(2025, 4, 5)
    )
    assert json.loads(body["messages"][1]["content"])["article_published_at"] == "2025-04-05"
