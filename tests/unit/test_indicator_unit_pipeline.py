from datetime import date

from core.unified_claim_pipeline import verify_registry_record
from schemas.claim import ClaimSchema
from schemas.claim_registry import ClaimRegistryRecord


class Extractor:
    def extract(self, source_sentence: str, **kwargs: object) -> ClaimSchema:
        raise AssertionError("incompatible enriched Claim must stop before reparse")


class Resolver:
    def __init__(self) -> None:
        self.calls = 0

    def resolve(self, claim: ClaimSchema, *, article_date: date) -> object:
        self.calls += 1
        return None


def test_indicator_unit_conflict_stops_before_official_lookup() -> None:
    source = "총인구 관련 예산은 100억원이다."
    claim = ClaimSchema(
        claim_id="C1",
        source_sentence=source,
        indicator="총인구",
        value=10_000_000_000,
        unit="원",
        time="2024",
        frequency="Y",
        calculation="DIRECT_VALUE",
        parse_status="AUTO_OK",
    )
    record = ClaimRegistryRecord(
        article_id="A1",
        sentence_id="1",
        article_published_at=date(2025, 1, 1),
        source_ref="indicator_unit_audit",
        claim=claim,
        slot_enrichment={
            "indicator_unit_status": "INDICATOR_UNIT_CONFLICT",
            "indicator_unit_reason_code": "INDICATOR_UNIT_MEASURE_MISMATCH",
        },
    )
    resolver = Resolver()

    entries = verify_registry_record(
        record,
        extractor=Extractor(),
        official_service=resolver,
    )

    assert entries[0].terminal_status == "HUMAN_REVIEW"
    assert entries[0].reason_code == "INDICATOR_UNIT_MEASURE_MISMATCH"
    assert resolver.calls == 0
