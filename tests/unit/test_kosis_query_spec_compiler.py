from datetime import date

from core.kosis_query_spec_compiler import compile_kosis_query_spec
from schemas.claim import ClaimSchema


def _claim(**updates) -> ClaimSchema:
    payload = {
        "claim_id": "C1", "source_sentence": "2024년 전국 취업자는 2800만 명이다.",
        "indicator": "취업자 수", "value": 28000000, "unit": "명", "time": "2024",
        "frequency": "Y", "region": "전국", "calculation": "DIRECT_VALUE", "parse_status": "AUTO_OK",
    }
    payload.update(updates)
    return ClaimSchema(**payload)


def test_compiles_coordinate_ready_direct_value_spec() -> None:
    spec = compile_kosis_query_spec(_claim(), article_date=date(2025, 1, 10))

    assert spec.readiness_status == "COORDINATE_READY"
    assert spec.measure_family == "PERSON"
    assert spec.unit_family == "PERSON"
    assert spec.period == "2024"
    assert spec.frequency == "년"
    assert spec.geography_scope == "NATIONAL"
    assert spec.required_evidence_cells == 1
    assert "취업자 수" in spec.search_terms


def test_compiles_ytd_trade_dimensions_without_inventing_coordinate() -> None:
    claim = _claim(
        source_sentence="올해 1~4월 스페인에 오징어를 2180톤 수출했다.", indicator="오징어 수출량",
        value=2180, unit="톤", time="2025-01/2025-04", frequency="YTD",
        dimension={"product": "오징어", "trade_partner": "스페인"},
    )

    spec = compile_kosis_query_spec(claim, article_date=date(2025, 5, 19))

    assert spec.period_mode == "CUMULATIVE"
    assert spec.measure_family == "QUANTITY"
    assert spec.dimensions == {"product": ["오징어"], "trade_partner": ["스페인"]}
    assert spec.official_route == "KOSIS_FIRST"


def test_missing_time_is_preverification_not_catalog_failure() -> None:
    spec = compile_kosis_query_spec(_claim(time=None), article_date=date(2025, 1, 10))

    assert spec.readiness_status == "PRE_VERIFICATION"
    assert "MISSING_TIME" in spec.readiness_reasons


def test_country_growth_uses_country_geography() -> None:
    spec = compile_kosis_query_spec(_claim(
        source_sentence="아일랜드는 1분기에 9.7% 성장했다.", indicator="경제성장률", value=9.7,
        unit="%", time="2025-Q1", frequency="Q", region="아일랜드",
    ), article_date=date(2025, 6, 1))

    assert spec.measure_family == "RATE"
    assert spec.geography_scope == "COUNTRY"
    assert spec.region == "아일랜드"


def test_query_spec_preserves_population_as_coordinate_search_constraint() -> None:
    spec = compile_kosis_query_spec(
        _claim(indicator="실업률", value=5.9, unit="%", population="청년"),
        article_date=date(2025, 1, 10),
    )

    assert spec.population == "청년"
    assert "청년" in spec.search_terms
