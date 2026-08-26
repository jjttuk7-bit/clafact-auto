from datetime import date

from core.unified_claim_pipeline import verify_registry_record
from schemas.claim import ClaimSchema
from schemas.claim_registry import ClaimRegistryRecord


class _Extractor:
    def extract(self, source_sentence: str, **kwargs: object) -> ClaimSchema:
        raise AssertionError("stored-slot direct type gate must not call extractor")


class _Resolver:
    def __init__(self) -> None:
        self.calls = 0

    def resolve(self, claim: ClaimSchema, *, article_date: date) -> object:
        self.calls += 1
        return None


def test_direct_type_gate_precedes_indicator_gate_and_official_lookup() -> None:
    source = "지난달 수출은 전년 동월 대비 10.3% 급감했다."
    record = ClaimRegistryRecord(
        article_id="A1",
        sentence_id="1",
        article_published_at=date(2025, 2, 1),
        source_ref="direct-value-type-order",
        claim=ClaimSchema(
            claim_id="C1",
            source_sentence=source,
            indicator="수출액",
            value=10.3,
            unit="%",
            time="2025-01",
            frequency="M",
            calculation="DIRECT_VALUE",
            parse_status="AUTO_OK",
        ),
        slot_enrichment={
            "target_link_status": "SOURCE_GROUNDED",
            "target_numeric_expression": "10.3%",
            "target_numeric_start": source.index("10.3%"),
            "target_numeric_end": source.index("10.3%") + len("10.3%"),
            "indicator_unit_status": "INDICATOR_REFINEMENT_REQUIRED",
        },
    )
    resolver = _Resolver()

    entries = verify_registry_record(
        record,
        extractor=_Extractor(),
        official_service=resolver,
        allow_structured_recovery=False,
    )

    assert entries[0].terminal_status == "HUMAN_REVIEW"
    assert entries[0].reason_code == "RECLASSIFY_TO_GROWTH_RATE"
    assert resolver.calls == 0


def test_stored_threshold_is_recovered_before_contract_check() -> None:
    source = "생산연령인구는 3000만명 아래로 내려간다."
    record = ClaimRegistryRecord(
        article_id="A2",
        sentence_id="1",
        article_published_at=date(2025, 2, 1),
        source_ref="direct-value-threshold-order",
        claim=ClaimSchema(
            claim_id="C2",
            source_sentence=source,
            indicator="생산연령인구",
            value=30_000_000,
            unit="명",
            time="2040",
            frequency="Y",
            calculation="THRESHOLD",
            parse_status="HOLD",
            parse_reason="MISSING_REQUIRED_SLOTS:condition",
        ),
        slot_enrichment={
            "target_link_status": "SOURCE_GROUNDED",
            "target_numeric_expression": "3000만명",
            "target_numeric_start": source.index("3000만명"),
            "target_numeric_end": source.index("3000만명") + len("3000만명"),
        },
    )
    resolver = _Resolver()

    entries = verify_registry_record(
        record,
        extractor=_Extractor(),
        official_service=resolver,
        allow_structured_recovery=False,
    )

    assert entries[0].claim.parse_status == "AUTO_OK"
    assert entries[0].claim.condition == {
        "operator": "LTE",
        "threshold_value": "30000000.0",
        "threshold_unit": "명",
    }
    assert resolver.calls == 1
