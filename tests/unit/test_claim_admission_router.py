import pytest

from core.claim_admission_router import route_claim_admission
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


@pytest.mark.parametrize(
    ("source", "updates", "label", "reason"),
    [
        (
            "지난달 제조업 취업자는 439만7000명이었다.",
            {},
            "KOSIS_PIPELINE_ELIGIBLE",
            "SINGLE_STATISTICAL_CLAIM",
        ),
        (
            "지난달 소비자물가는 2.2% 올랐다.",
            {"time": None},
            "CONTEXT_REQUIRED",
            "MISSING_TIME_CONTEXT",
        ),
        (
            "취업자는 100명이고 실업자는 20명이었다.",
            {},
            "MULTI_CLAIM_SPLIT_REQUIRED",
            "MULTIPLE_NUMERIC_CLAUSES",
        ),
        (
            "현대차는 지난해 수출액이 10% 늘었다.",
            {},
            "NON_KOSIS_OR_PRIVATE",
            "PRIVATE_OR_COMPANY_SOURCE",
        ),
        (
            "한국은행은 올해 성장률이 1%일 것으로 전망했다.",
            {},
            "FORECAST_OPINION_UNVERIFIABLE",
            "FORECAST_OR_OPINION",
        ),
        (
            "정부는 1인당 15만원의 소비쿠폰을 지급한다.",
            {},
            "NOT_A_VERIFIABLE_CLAIM",
            "POLICY_OR_DEFINITION",
        ),
    ],
)
def test_routes_candidate_to_one_admission_label(
    source: str, updates: dict[str, object], label: str, reason: str
) -> None:
    decision = route_claim_admission(claim(source, **updates))

    assert decision.label == label
    assert decision.reason_code == reason


def test_non_auto_parse_requires_context_without_promoting_to_kosis() -> None:
    decision = route_claim_admission(claim(
        "작년 수출은 역대 최대였다.",
        value=None,
        unit=None,
        parse_status="HOLD",
        parse_reason="CLAIM_PARSE_UNCERTAIN",
    ))

    assert decision.label == "CONTEXT_REQUIRED"
    assert decision.reason_code == "PARSE_UNCERTAIN"
