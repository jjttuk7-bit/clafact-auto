from core.claim_disposition import classify_claim_disposition
from schemas.claim import ClaimSchema


def test_unsupported_comparison_stays_context_insufficient_despite_complete_slots() -> None:
    result = classify_claim_disposition(ClaimSchema(
        claim_id="C",
        source_sentence="The difference was 52.35 USD 100m.",
        indicator="export value difference",
        value=52.35,
        unit="USD 100m",
        time="2024",
        frequency="annual",
        calculation="DIFFERENCE",
        comparison={"type": "DIFFERENCE"},
        condition={"direction": "INCREASE"},
        parse_status="HOLD",
        parse_reason="CLAIM_COMPARISON_UNSUPPORTED",
    ))

    assert result.disposition == "SOURCE_CONTEXT_INSUFFICIENT"
    assert result.reason_code == "CLAIM_COMPARISON_UNSUPPORTED"
    assert result.next_route == "CONTEXT_REVIEW"
