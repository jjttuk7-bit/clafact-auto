from core.claim_slot_enricher import enrich_claim_slots
from schemas.claim import ClaimSchema


class EmptyComparisonExtractor:
    def extract(self, source_sentence: str) -> ClaimSchema:
        return ClaimSchema(
            claim_id="provider",
            source_sentence=source_sentence,
            indicator="배추 물가",
            value=-34.5,
            unit="%",
            time="2025년 10월",
            comparison={},
            calculation="GROWTH_RATE",
            condition={},
            parse_status="AUTO_OK",
        )


def test_slot_enricher_holds_growth_when_provider_returns_empty_comparison_map() -> None:
    claim = ClaimSchema(
        claim_id="registry:x:A1:1",
        source_sentence="2025년 10월 배추 물가가 34.5% 하락했다.",
        indicator="배추 물가",
        value=-34.5,
        unit="%",
        time="2025년 10월",
        parse_status="AUTO_OK",
    )

    result = enrich_claim_slots(claim, EmptyComparisonExtractor())

    assert result.claim.parse_status == "HOLD"
    assert result.catalog_search_ready is False
    assert result.reason_code == "MISSING_COMPARISON_FOR_GROWTH_RATE"
