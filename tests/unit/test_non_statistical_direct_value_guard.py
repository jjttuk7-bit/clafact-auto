from core.source_observation_guard import observation_preverification_reason
from schemas.claim import ClaimSchema


def _claim(source: str, indicator: str = "금액") -> ClaimSchema:
    return ClaimSchema(
        claim_id="c1", source_sentence=source, indicator=indicator,
        value=4_000_000_000_000, unit="원", time="2022",
        calculation="DIRECT_VALUE", parse_status="AUTO_OK",
    )


def test_blocks_private_transaction_amounts_that_are_not_official_statistics() -> None:
    assert observation_preverification_reason(
        _claim("LIG넥스원은 UAE와 약 4조원 규모 수출 계약을 따냈다.", "수출 계약액")
    ) == "NON_STATISTICAL_PRIVATE_TRANSACTION"
    assert observation_preverification_reason(
        _claim("회사는 자본금 4억8000만원 규모로 국내 법인을 설립했다.", "자본금")
    ) == "NON_STATISTICAL_PRIVATE_TRANSACTION"


def test_blocks_product_price_and_policy_threshold_but_not_observed_statistics() -> None:
    assert observation_preverification_reason(
        _claim("신형 차량의 판매 가격은 8000만원이다.", "판매 가격")
    ) == "NON_STATISTICAL_PRODUCT_PRICE"
    assert observation_preverification_reason(
        _claim("고가 법인차 지정 기준은 8000만원 이상이다.", "지정 기준")
    ) == "NON_STATISTICAL_POLICY_THRESHOLD"
    assert observation_preverification_reason(
        _claim("지난해 자동차 수출액은 4조원으로 집계됐다.", "수출액")
    ) is None
    assert observation_preverification_reason(
        _claim("지난해 소비자물가지수는 3.2%로 나타났다.", "소비자물가지수")
    ) is None
