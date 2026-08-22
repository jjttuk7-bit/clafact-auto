from datetime import date

from core.unified_claim_pipeline import verify_registry_record
from schemas.claim import ClaimSchema
from schemas.claim_registry import ClaimRegistryRecord


class _Extractor:
    def extract(self, source_sentence: str, **kwargs) -> ClaimSchema:
        return ClaimSchema(
            claim_id="temporary",
            source_sentence=source_sentence,
            indicator="고용률",
            value=70,
            unit="%",
            time=None,
            calculation="DIRECT_VALUE",
            parse_status="AUTO_OK",
        )


class _OfficialService:
    def __init__(self) -> None:
        self.calls = 0

    def resolve(self, claim: ClaimSchema, *, article_date: date) -> object:
        self.calls += 1
        return {"route_status": "AUTO"}


def test_missing_required_slot_is_recorded_before_official_lookup() -> None:
    record = ClaimRegistryRecord(
        article_id="A1",
        sentence_id="1",
        article_published_at=date(2025, 3, 1),
        source_ref="registry",
        claim=ClaimSchema(
            claim_id="parent",
            source_sentence="고용률은 70%였다.",
            indicator="고용률",
            value=70,
            unit="%",
            time=None,
            calculation="DIRECT_VALUE",
            parse_status="AUTO_OK",
        ),
    )
    official = _OfficialService()

    entries = verify_registry_record(
        record,
        extractor=_Extractor(),
        official_service=official,
    )

    assert official.calls == 0
    assert entries[0].terminal_status == "HUMAN_REVIEW"
    assert entries[0].slot_audit.eligible_for_official_search is False
    assert entries[0].slot_audit.by_slot("time").status == "MISSING"
