from datetime import date

from core.claim_reparse_batch import reparse_non_auto_records
from schemas.claim import ClaimSchema
from schemas.claim_registry import ClaimRegistryRecord


def _record(status: str, *, sentence_id: str = "1") -> ClaimRegistryRecord:
    return ClaimRegistryRecord(
        article_id="A1",
        sentence_id=sentence_id,
        article_published_at=date(2025, 4, 1),
        source_ref="gold_standard_v1",
        claim=ClaimSchema(
            claim_id=f"gold-{sentence_id}",
            source_sentence="지난달 취업자 수는 2,804만1천 명이었다.",
            indicator="취업자 수",
            value=28_041_000,
            unit="명",
            parse_status=status,
            parse_reason="기존 상세 판단",
        ),
    )


class Extractor:
    def __init__(self) -> None:
        self.calls: list[date | None] = []

    def extract(self, source_sentence: str, *, article_published_at=None) -> ClaimSchema:
        self.calls.append(article_published_at)
        return ClaimSchema(
            claim_id="provider-id",
            source_sentence=source_sentence,
            indicator="취업자 수",
            value=28_041_000,
            unit="명",
            time="지난달",
            frequency="월",
            region="전국",
            calculation="DIRECT_VALUE",
            parse_status="AUTO_OK",
        )


def test_reparse_non_auto_preserves_gold_identity_and_resolves_relative_time() -> None:
    extractor = Extractor()

    records, summary = reparse_non_auto_records([_record("HOLD")], extractor)

    reparsed = records[0]
    assert reparsed.claim.claim_id == "gold-1"
    assert reparsed.claim.source_sentence == "지난달 취업자 수는 2,804만1천 명이었다."
    assert reparsed.claim.time == "2025년 3월"
    assert reparsed.claim.parse_status == "AUTO_OK"
    assert reparsed.source_ref == "gold_standard_v1_openai_reparse_v1"
    assert reparsed.slot_enrichment == {
        "stage": "CLAIM_REPARSE",
        "source_parse_status": "HOLD",
        "source_parse_reason_detail": "기존 상세 판단",
        "result_parse_status": "AUTO_OK",
        "reason_code": None,
    }
    assert extractor.calls == [date(2025, 4, 1)]
    assert summary == {
        "total_records": 1,
        "selected_records": 1,
        "reparsed_auto_ok": 1,
        "reparsed_hold": 0,
        "reparse_errors": 0,
        "preserved_auto_ok": 0,
    }


def test_reparse_batch_does_not_send_existing_auto_ok_claims() -> None:
    extractor = Extractor()
    source = _record("AUTO_OK")

    records, summary = reparse_non_auto_records([source], extractor)

    assert records == [source]
    assert extractor.calls == []
    assert summary["preserved_auto_ok"] == 1


def test_reparse_batch_routes_provider_failure_to_auditable_hold() -> None:
    class FailingExtractor:
        def extract(self, *_args, **_kwargs):
            raise RuntimeError("secret response must not be persisted")

    records, summary = reparse_non_auto_records([_record("HUMAN_REVIEW")], FailingExtractor())

    assert records[0].claim.parse_status == "HOLD"
    assert records[0].claim.parse_reason == "CLAIM_REPARSE_FAILED"
    assert records[0].slot_enrichment == {
        "stage": "CLAIM_REPARSE",
        "source_parse_status": "HUMAN_REVIEW",
        "source_parse_reason_detail": "기존 상세 판단",
        "result_parse_status": "HOLD",
        "reason_code": "CLAIM_REPARSE_FAILED",
        "error_type": "RuntimeError",
    }
    assert "secret response" not in str(records[0].model_dump())
    assert summary["reparse_errors"] == 1


def test_reparse_batch_preserves_input_order_with_workers() -> None:
    records, _summary = reparse_non_auto_records(
        [_record("HOLD", sentence_id=str(index)) for index in range(5)],
        Extractor(),
        workers=3,
    )

    assert [record.sentence_id for record in records] == ["0", "1", "2", "3", "4"]


def test_reparse_batch_aborts_on_authentication_failure() -> None:
    class FailingExtractor:
        def extract(self, *_args, **_kwargs):
            from core.openai_function_claim_extractor import OpenAIAuthenticationError

            raise OpenAIAuthenticationError("OPENAI_AUTHENTICATION_FAILED")

    import pytest

    with pytest.raises(Exception, match="OPENAI_AUTHENTICATION_FAILED"):
        reparse_non_auto_records([_record("HOLD")], FailingExtractor())
