from core.claim_slot_enricher import enrich_claim_slots
from schemas.claim import ClaimSchema


class FakeExtractor:
    def __init__(self, result: ClaimSchema) -> None:
        self.result = result

    def extract(self, source_sentence: str) -> ClaimSchema:
        return self.result


def _claim(**updates) -> ClaimSchema:
    values = {
        "claim_id": "registry:source:A1:1",
        "source_sentence": "2025년 10월 배추 물가는 전년 동월 대비 34.5% 하락했다.",
        "indicator": "배추 물가",
        "value": -34.5,
        "unit": "%",
        "time": "2025년 10월",
        "frequency": "월",
        "parse_status": "AUTO_OK",
    }
    values.update(updates)
    return ClaimSchema(**values)


def _extracted(**updates) -> ClaimSchema:
    values = {
        "claim_id": "provider-id",
        "source_sentence": "provider source",
        "indicator": "다른 지표",
        "value": 999.0,
        "unit": "명",
        "time": "2020년",
        "comparison": {"type": "YEAR_OVER_YEAR"},
        "calculation": "GROWTH_RATE",
        "condition": {"seasonal_adjustment": "원계열"},
        "parse_status": "AUTO_OK",
    }
    values.update(updates)
    return ClaimSchema(**values)


def test_slot_enricher_updates_only_target_slots_and_preserves_source_claim() -> None:
    result = enrich_claim_slots(_claim(), FakeExtractor(_extracted()))

    assert result.claim.indicator == "배추 물가"
    assert result.claim.value == -34.5
    assert result.claim.comparison == {"type": "YEAR_OVER_YEAR"}
    assert result.claim.calculation == "GROWTH_RATE"
    assert result.claim.condition == {"seasonal_adjustment": "원계열"}
    assert result.catalog_search_ready is True
    assert result.reason_code is None


def test_slot_enricher_holds_when_structured_output_has_no_calculation() -> None:
    result = enrich_claim_slots(_claim(), FakeExtractor(_extracted(calculation=None)))

    assert result.claim.parse_status == "HOLD"
    assert result.catalog_search_ready is False
    assert result.reason_code == "MISSING_CALCULATION"


def test_slot_enricher_holds_growth_claim_without_comparison() -> None:
    result = enrich_claim_slots(
        _claim(source_sentence="2025년 10월 배추 물가가 34.5% 하락했다."),
        FakeExtractor(_extracted(comparison=None, calculation="GROWTH_RATE")),
    )

    assert result.claim.parse_status == "HOLD"
    assert result.catalog_search_ready is False
    assert result.reason_code == "MISSING_COMPARISON_FOR_GROWTH_RATE"
