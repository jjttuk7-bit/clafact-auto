from datetime import date

from core.direct_value_claim_reclassifier import reclassify_direct_value_claim
from core.direct_value_verification_type import classify_direct_value_target
from core.source_indicator_refinement import refine_source_indicator
from core.source_observation_guard import observation_preverification_reason
from core.unified_claim_pipeline import verify_registry_record
from schemas.claim import ClaimSchema
from schemas.claim_registry import ClaimRegistryRecord


def _claim(source: str, indicator: str, value: float, unit: str) -> ClaimSchema:
    return ClaimSchema(
        claim_id="C1", source_sentence=source, indicator=indicator, value=value,
        unit=unit, time="2025-Q1", frequency="Q", calculation="DIRECT_VALUE",
        parse_status="AUTO_OK",
    )


def test_refines_explicit_source_measure_instead_of_generic_indicator() -> None:
    cases = [
        ("순수출 성장 기여도는 올해 1분기 0.3%포인트로 집계됐다.", "수출액", 0.3, "%p", "0.3%포인트", "순수출 성장 기여도"),
        ("순수출의 성장 기여도는 0% 수준이었다.", "수출액", 0.0, "%", "0%", "순수출 성장 기여도"),
        ("올해 1~4월 스페인에 오징어를 2180톤 수출했다.", "수출액", 2180, "톤", "2180톤", "오징어 수출량"),
        ("2020년 인구주택총조사의 최종 응답률은 96.3%였다.", "총인구", 96.3, "%", "96.3%", "인구주택총조사 최종 응답률"),
        ("생활물가지수는 지난해 10월 1.2%로 집계됐다.", "생활물가지수", 1.2, "%", "1.2%", "생활물가 상승률"),
    ]
    for source, indicator, value, unit, expression, expected in cases:
        refined = refine_source_indicator(
            _claim(source, indicator, value, unit), target_expression=expression,
        )
        assert refined.indicator == expected


def test_record_refinement_repairs_source_bound_time_and_region() -> None:
    trade_source = "올해 1~4월 우리나라는 스페인에 오징어를 2180톤 수출했다."
    trade = _claim(trade_source, "수출액", 2180, "톤").model_copy(update={"time": "2024", "frequency": "Y"})
    trade_record = ClaimRegistryRecord(
        article_id="A2", sentence_id="1", article_published_at=date(2025, 5, 19),
        source_ref="fixture", claim=trade,
        slot_enrichment={"target_numeric_role": "대상값"},
    )
    from core.source_indicator_refinement import apply_source_indicator_refinement
    trade_refined = apply_source_indicator_refinement(trade_record, target_expression="2180톤")
    assert trade_refined.claim.time == "2025-01/2025-04"
    assert trade_refined.claim.frequency == "YTD"

    growth_source = "대미 수출이 급증한 덕에 아일랜드는 1분기에 9.7% 성장했다."
    growth = _claim(growth_source, "수출액", 9.7, "%").model_copy(update={"dimension": {"trade_partner": "미국"}})
    growth_record = ClaimRegistryRecord(
        article_id="A3", sentence_id="1", article_published_at=date(2025, 6, 23),
        source_ref="fixture", claim=growth,
        slot_enrichment={"target_numeric_role": "대상값"},
    )
    growth_refined = apply_source_indicator_refinement(growth_record, target_expression="9.7%")
    assert growth_refined.claim.indicator == "경제성장률"
    assert growth_refined.claim.region == "아일랜드"
    assert growth_refined.claim.dimension is None

def test_share_is_detected_from_correspondence_phrases() -> None:
    cases = [
        ("한국 인구의 20%가 65세 이상이다.", "20%"),
        ("이 규모는 우리나라 수출의 1.9%에 해당한다.", "1.9%"),
    ]
    for source, expression in cases:
        result = classify_direct_value_target(
            source, target_expression=expression, unit="%", indicator="총인구",
        )
        assert result.type_code == "SHARE"


def test_forecast_effect_language_is_not_observed_level() -> None:
    cases = [
        "예산 감액이 성장률을 0.06%p 낮출 것으로 분석했다.",
        "추경안은 연간 성장률을 0.2%포인트 올릴 것”이라고 했다.",
        "정부가 최근 발표한 추경안은 연간 성장률을 0.2%포인트 정도 올릴 것”이라고 했다.",
    ]
    for source in cases:
        claim = _claim(source, "경제성장률", 0.2, "%p")
        assert observation_preverification_reason(claim) == "NON_OBSERVED_FORECAST"


def test_policy_tariff_rate_is_not_sent_to_kosis_as_trade_amount() -> None:
    row = {
        "자식Claim번호": "C1", "원본부모Claim번호": "P1",
        "원문": "지난 4월부터 모든 수입차에 25% 관세를 매겼다.",
        "지표": "수입액", "기사값": "25", "단위": "%", "기준시점": "2025-04",
        "주기": "M", "계산방식": "DIRECT_VALUE", "대상수치표현": "25%",
        "개선후사유": "INDICATOR_REFINEMENT_REQUIRED", "사용집합": "RULE_DISCOVERY",
    }
    decision = reclassify_direct_value_claim(row)
    assert decision.top_level_result == "EXCLUDE_FROM_KOSIS"
    assert decision.result_code == "EXCLUDE_POLICY_RATE"


def test_pipeline_rechecks_stale_audit_after_source_refinement() -> None:
    source = "순수출 성장 기여도는 올해 1분기 0.3%포인트로 집계됐다."
    claim = _claim(source, "수출액", 0.3, "%p")
    record = ClaimRegistryRecord(
        article_id="A1", sentence_id="1", article_published_at=date(2025, 4, 24),
        source_ref="fixture", claim=claim,
        slot_enrichment={
            "target_link_status": "SOURCE_GROUNDED",
            "target_numeric_expression": "0.3%포인트",
            "target_numeric_role": "대상값",
            "target_numeric_start": source.index("0.3%포인트"),
            "target_numeric_end": source.index("0.3%포인트") + len("0.3%포인트"),
            "indicator_unit_status": "INDICATOR_REFINEMENT_REQUIRED",
        },
    )

    class Extractor:
        pass

    class Resolver:
        def __init__(self) -> None:
            self.indicator = ""

        def resolve(self, claim: ClaimSchema, *, article_date: date) -> dict[str, str]:
            self.indicator = claim.indicator or ""
            return {"route_status": "HOLD", "reason_code": "TEST_AFTER_REFINEMENT"}

    resolver = Resolver()
    entry = verify_registry_record(
        record, extractor=Extractor(), official_service=resolver,
        allow_structured_recovery=False,
    )[0]
    assert resolver.indicator == "순수출 성장 기여도"
    assert entry.reason_code == "TEST_AFTER_REFINEMENT"
