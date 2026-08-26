from core.source_observation_guard import observation_preverification_reason
from schemas.claim import ClaimSchema


def _claim(source: str, indicator: str, value: float = 1.0, unit: str = "%") -> ClaimSchema:
    return ClaimSchema(
        claim_id="c", source_sentence=source, indicator=indicator,
        value=value, unit=unit, time="2025", calculation="DIRECT_VALUE",
        parse_status="AUTO_OK",
    )


def test_contract_noun_policy_marker_and_normative_benchmark_are_excluded() -> None:
    assert observation_preverification_reason(
        _claim("30억달러 규모 FA-50 수출 계약은 변곡점이었다.", "수출액", 3e9, "달러")
    ) == "NON_STATISTICAL_PRIVATE_TRANSACTION"
    assert observation_preverification_reason(
        _claim("8000만원 이상 법인차에 연두색 표지판을 부착한다.", "수입액", 8e7, "원")
    ) == "NON_STATISTICAL_POLICY_THRESHOLD"
    assert observation_preverification_reason(
        _claim("한국 경제는 2%는 성장해야 한다.", "경제성장률", 2.0)
    ) == "NON_STATISTICAL_POLICY_THRESHOLD"


def test_announced_projection_is_still_forecast_not_observed_value() -> None:
    assert observation_preverification_reason(
        _claim("올해 성장률이 1.7%가 될 것이라고 발표했다.", "경제성장률", 1.7)
    ) == "NON_OBSERVED_FORECAST"
