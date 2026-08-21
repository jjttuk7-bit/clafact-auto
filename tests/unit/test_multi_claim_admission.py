from core.claim_admissibility import classify_admissibility


def test_classifies_explicit_multi_claim_requirement_for_recovery() -> None:
    result = classify_admissibility("MULTI_CLAIM_SPLIT_REQUIRED", "HOLD")

    assert result.route == "MULTI_CLAIM_SPLIT_REQUIRED"
    assert result.reason_code == "MULTI_CLAIM_SPLIT_REQUIRED"
