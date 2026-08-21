import json
from datetime import date

from core.admission_recovery import recover_registry_record
from schemas.claim import ClaimSchema
from schemas.claim_registry import ClaimRegistryRecord


class _ContextExtractor:
    def extract(self, source_sentence: str, *, article_published_at=None) -> ClaimSchema:
        payload = json.loads(source_sentence)
        assert payload["target_sentence"] == "2024년 고용률은 61%였다."
        assert "2023년 고용률" in payload["article_context"]
        return ClaimSchema(
            claim_id="temporary",
            source_sentence=source_sentence,
            indicator="고용률",
            value=61,
            unit="%",
            time="2024년",
            frequency="년",
            calculation="DIRECT_VALUE",
            parse_status="AUTO_OK",
        )


class _Service:
    def resolve(self, claim, *, article_date):
        return {"route_status": "AUTO", "reason_code": "WITHIN_TOLERANCE"}


def test_context_reparse_preserves_the_target_claim_identity_and_source() -> None:
    claim = ClaimSchema(
        claim_id="target-claim",
        source_sentence="2024년 고용률은 61%였다.",
        indicator="고용률",
        value=61,
        unit="%",
        time="2024년",
        frequency="년",
        calculation="DIRECT_VALUE",
        parse_status="HOLD",
        parse_reason="SOURCE_CONTEXT_UNCLEAR",
    )
    record = ClaimRegistryRecord(
        article_id="A1",
        sentence_id="2",
        article_published_at=date(2025, 1, 10),
        source_ref="test",
        claim=claim,
    )

    result = recover_registry_record(
        record,
        extractor=_ContextExtractor(),
        official_service=_Service(),
        article_context="2023년 고용률은 60%였고 2024년 고용률은 61%였다.",
    )

    recovered = result.entries[0].record.claim
    assert result.recovery_action == "CONTEXT_REPARSE"
    assert recovered.claim_id == "target-claim"
    assert recovered.source_sentence == "2024년 고용률은 61%였다."
    assert recovered.value == 61
