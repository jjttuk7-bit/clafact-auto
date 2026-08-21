from core.claim_admission_pipeline import ClaimAdmissionPipeline
from schemas.claim import ClaimSchema


def claim(sentence: str, **updates: object) -> ClaimSchema:
    payload: dict[str, object] = {
        "claim_id": "C-1",
        "source_sentence": sentence,
        "indicator": "취업자 수",
        "value": 100.0,
        "unit": "명",
        "time": "2025-05",
        "frequency": "월",
        "calculation": "DIRECT_VALUE",
        "parse_status": "AUTO_OK",
    }
    payload.update(updates)
    return ClaimSchema.model_validate(payload)


def test_eligible_claim_is_the_only_route_that_calls_official_resolver() -> None:
    official_calls: list[str] = []
    pipeline = ClaimAdmissionPipeline(
        official_resolver=lambda candidate: official_calls.append(candidate.claim_id) or {"ok": True}
    )

    executions = pipeline.process(claim("지난달 제조업 취업자는 100명이었다."))

    assert official_calls == ["C-1"]
    assert executions[0].result.route_status == "OFFICIAL_VERIFICATION_STARTED"
    assert executions[0].official_result == {"ok": True}


def test_context_route_reparses_once_then_reenters_admission() -> None:
    official_calls: list[str] = []
    pipeline = ClaimAdmissionPipeline(
        official_resolver=lambda candidate: official_calls.append(candidate.claim_id) or {"ok": True},
        context_reparser=lambda candidate: candidate.model_copy(update={"time": "2025-05"}),
    )

    executions = pipeline.process(claim("지난달 취업자는 100명이었다.", time=None))

    assert official_calls == ["C-1"]
    assert executions[0].result.events[-1].stage == "OFFICIAL_VERIFICATION"
    assert [event.stage for event in executions[0].result.events] == [
        "CLAIM_ADMISSION", "CLAIM_CONTEXT_REPARSE", "CLAIM_ADMISSION", "OFFICIAL_VERIFICATION"
    ]


def test_multi_route_splits_children_and_readmits_each_child() -> None:
    official_calls: list[str] = []
    pipeline = ClaimAdmissionPipeline(
        official_resolver=lambda candidate: official_calls.append(candidate.claim_id) or {"ok": True},
        child_parser=lambda parent, text, child_id: parent.model_copy(
            update={"claim_id": child_id, "source_sentence": text}
        ),
    )

    executions = pipeline.process(claim("취업자는 100명이고 실업자는 20명이었다."))

    assert official_calls == ["C-1__split_1", "C-1__split_2"]
    assert [entry.result.decision.label for entry in executions] == [
        "KOSIS_PIPELINE_ELIGIBLE", "KOSIS_PIPELINE_ELIGIBLE"
    ]


def test_excluded_route_never_calls_official_resolver() -> None:
    official_calls: list[str] = []
    pipeline = ClaimAdmissionPipeline(
        official_resolver=lambda candidate: official_calls.append(candidate.claim_id) or {"ok": True}
    )

    executions = pipeline.process(claim("정부는 1인당 15만원의 소비쿠폰을 지급한다."))

    assert official_calls == []
    assert executions[0].result.route_status == "ADMISSION_ROUTED"
    assert executions[0].result.decision.label == "NOT_A_VERIFIABLE_CLAIM"


def test_pipeline_uses_injected_admission_router() -> None:
    from schemas.claim_admission import AdmissionDecision

    pipeline = ClaimAdmissionPipeline(
        official_resolver=lambda _candidate: {"ok": True},
        admission_router=lambda _candidate: AdmissionDecision(
            label="NOT_A_VERIFIABLE_CLAIM", reason_code="GOLDSET_CLASSIFIER"
        ),
    )

    execution = pipeline.process(claim("지난달 제조업 취업자는 100명이었다."))[0]

    assert execution.result.decision.reason_code == "GOLDSET_CLASSIFIER"
    assert execution.official_result is None

def test_structural_multi_guard_prevents_an_injected_eligible_router_from_calling_kosis() -> None:
    from schemas.claim_admission import AdmissionDecision

    official_calls: list[str] = []
    pipeline = ClaimAdmissionPipeline(
        official_resolver=lambda candidate: official_calls.append(candidate.claim_id) or {"ok": True},
        admission_router=lambda _candidate: AdmissionDecision(
            label="KOSIS_PIPELINE_ELIGIBLE", reason_code="MODEL_ELIGIBLE"
        ),
    )

    execution = pipeline.process(claim(
        "지난달 제조업 취업자는 439만7000명으로 전년 동월 대비 12만4000명 줄었다."
    ))[0]

    assert official_calls == []
    assert execution.result.decision.label == "MULTI_CLAIM_SPLIT_REQUIRED"
    assert execution.result.decision.reason_code == "STRUCTURAL_MULTI_CLAIM"

def test_historical_reference_without_a_current_value_requires_context_before_kosis() -> None:
    from schemas.claim_admission import AdmissionDecision

    official_calls: list[str] = []
    pipeline = ClaimAdmissionPipeline(
        official_resolver=lambda candidate: official_calls.append(candidate.claim_id) or {"ok": True},
        admission_router=lambda _candidate: AdmissionDecision(
            label="KOSIS_PIPELINE_ELIGIBLE", reason_code="MODEL_ELIGIBLE"
        ),
    )

    execution = pipeline.process(claim(
        "생활물가지수는 지난해 10월(1.2%)을 저점으로 꾸준히 오름세를 보이고 있다."
    ))[0]

    assert official_calls == []
    assert execution.result.decision.label == "CONTEXT_REQUIRED"
    assert execution.result.decision.reason_code == "HISTORICAL_REFERENCE_CONTEXT"

def test_structural_multi_claim_splits_and_readmits_both_children() -> None:
    official_calls: list[str] = []
    pipeline = ClaimAdmissionPipeline(
        official_resolver=lambda candidate: official_calls.append(candidate.claim_id) or {"ok": True},
        child_parser=lambda parent, text, child_id: parent.model_copy(
            update={"claim_id": child_id, "source_sentence": text}
        ),
    )

    executions = pipeline.process(claim(
        "지난달 제조업 취업자는 439만7000명으로 전년 동월 대비 12만4000명 줄었다."
    ))

    assert official_calls == ["C-1__split_1", "C-1__split_2"]
    assert [entry.claim.source_sentence for entry in executions] == [
        "지난달 제조업 취업자는 439만7000명이다.",
        "지난달 제조업 취업자는 전년 동월 대비 12만4000명 줄었다.",
    ]