from core.claim_output_contract import CLAIM_OUTPUT_FIELD_NAMES, claim_output_json_schema
from core.hcx_claim_extractor import SYSTEM_PROMPT, build_structured_claim_request


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