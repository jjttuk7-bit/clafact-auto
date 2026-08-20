from schemas.claim_admission import AdmissionDecision, AdmissionEvent, AdmissionRouteResult


def test_admission_contract_preserves_decision_and_audit_event() -> None:
    decision = AdmissionDecision(
        label="CONTEXT_REQUIRED",
        reason_code="MISSING_TIME_CONTEXT",
    )
    event = AdmissionEvent(
        stage="CLAIM_ADMISSION",
        claim_id="C-1",
        label=decision.label,
        reason_code=decision.reason_code,
    )

    result = AdmissionRouteResult(
        claim_id="C-1",
        route_status="ADMISSION_ROUTED",
        decision=decision,
        events=[event],
    )

    assert result.route_status == "ADMISSION_ROUTED"
    assert result.decision.label == "CONTEXT_REQUIRED"
    assert result.events[0].stage == "CLAIM_ADMISSION"


def test_eligible_admission_is_not_an_official_verdict() -> None:
    result = AdmissionRouteResult(
        claim_id="C-1",
        route_status="ADMISSION_ROUTED",
        decision=AdmissionDecision(
            label="KOSIS_PIPELINE_ELIGIBLE",
            reason_code="SINGLE_STATISTICAL_CLAIM",
        ),
        events=[],
    )

    assert result.decision.label == "KOSIS_PIPELINE_ELIGIBLE"
    assert not hasattr(result, "verdict")
