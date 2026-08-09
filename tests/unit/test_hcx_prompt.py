from core.hcx_claim_extractor import SYSTEM_PROMPT


def test_structured_prompt_marks_year_on_year_as_growth_rate() -> None:
    assert "GROWTH_RATE" in SYSTEM_PROMPT
    assert "same-month-last-year" in SYSTEM_PROMPT


def test_structured_prompt_routes_multiple_independent_values_to_review() -> None:
    assert "HUMAN_REVIEW" in SYSTEM_PROMPT
    assert "independent" in SYSTEM_PROMPT


def test_structured_prompt_requires_negative_sign_for_explicit_decrease() -> None:
    assert "negative" in SYSTEM_PROMPT
    assert "decrease" in SYSTEM_PROMPT
