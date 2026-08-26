from schemas.claim import ClaimSchema

from core.direct_value_child_guard import (
    apply_direct_value_child_guard,
    direct_value_child_preverification_reason,
)


def _claim(source: str, *, indicator: str = "취업자", value: float = 1.0, unit: str = "명") -> ClaimSchema:
    return ClaimSchema(
        claim_id="direct-child",
        source_sentence=source,
        indicator=indicator,
        value=value,
        unit=unit,
        time="2025-02",
        frequency="M",
        calculation="DIRECT_VALUE",
        parse_status="AUTO_OK",
    )


def test_blocks_change_amount_misclassified_as_direct_value() -> None:
    source = "청년층 취업자는 20만6000명 줄었다."
    claim = _claim(source, value=206_000)

    assert direct_value_child_preverification_reason(
        claim, target_expression="20만6000명"
    ) == "RECLASSIFY_TO_DIFFERENCE"


def test_blocks_industry_coordinate_when_child_lost_source_dimension() -> None:
    source = "지난달 건설업 취업자는 190만9000명으로 집계됐다."
    claim = _claim(source, value=1_909_000)

    assert direct_value_child_preverification_reason(
        claim, target_expression="190만9000명"
    ) == "SOURCE_TARGET_DIMENSION_MISSING:건설업"


def test_blocks_education_coordinate_when_child_lost_source_population() -> None:
    source = "지난 1분기 기준 30대 고졸 실업률은 4.2%인 반면, 대졸 이상은 2.4%에 그쳤다."
    claim = _claim(source, indicator="실업률", value=2.4, unit="%")

    assert direct_value_child_preverification_reason(
        claim, target_expression="2.4%"
    ) == "SOURCE_TARGET_DIMENSION_MISSING:대졸 이상"


def test_allows_direct_total_and_preserved_industry_dimension() -> None:
    total = _claim("지난달 취업자는 2888만7000명으로 집계됐다.", value=28_887_000)
    industry = _claim(
        "지난달 건설업 취업자는 190만9000명으로 집계됐다.",
        indicator="건설업 취업자",
        value=1_909_000,
    )

    assert direct_value_child_preverification_reason(
        total, target_expression="2888만7000명"
    ) is None
    assert direct_value_child_preverification_reason(
        industry, target_expression="190만9000명"
    ) is None


def test_blocks_growth_rate_misclassified_as_direct_value() -> None:
    source = "지난달 수출은 전년 동월 대비 10.3% 급감했다."
    claim = _claim(source, indicator="수출액", value=10.3, unit="%")

    assert direct_value_child_preverification_reason(
        claim, target_expression="10.3%"
    ) == "RECLASSIFY_TO_GROWTH_RATE"

def test_recovers_threshold_condition_from_source() -> None:
    source = "생산연령인구는 3000만명 아래로 내려간다."
    claim = _claim(source, indicator="생산연령인구", value=30_000_000, unit="명")

    recovered = apply_direct_value_child_guard(
        claim, target_expression="3000만명"
    )

    assert recovered.calculation == "THRESHOLD"
    assert recovered.condition == {
        "operator": "LTE",
        "threshold_value": "30000000.0",
        "threshold_unit": "명",
    }
    assert recovered.parse_status == "AUTO_OK"


def test_clears_false_threshold_classification_for_plain_level() -> None:
    source = "지난달 ICT 무역 수지는 58억1000만달러 흑자였다."
    claim = _claim(source, indicator="무역수지", value=5_810_000_000, unit="달러")
    claim = claim.model_copy(update={"calculation": "THRESHOLD"})

    recovered = apply_direct_value_child_guard(
        claim, target_expression="58억1000만달러"
    )

    assert recovered.calculation == "DIRECT_VALUE"
    assert recovered.condition is None

def test_target_grounding_allows_source_whitespace_inside_expression() -> None:
    source = "수출액은 480억 달러로 집계됐다."
    claim = _claim(source, indicator="수출액", value=480.0, unit="USD 100m")

    assert direct_value_child_preverification_reason(
        claim, target_expression="480억달러"
    ) is None