from dataclasses import dataclass
from datetime import date

from core.context_claim_reparse_batch import reparse_records_with_limited_context
from schemas.claim import ClaimSchema
from schemas.claim_registry import ClaimRegistryRecord


@dataclass
class ContextExtractor:
    response: ClaimSchema
    received_context: str | None = None

    def extract(
        self,
        source_sentence: str,
        *,
        article_published_at: date | None = None,
        article_context: str | None = None,
    ) -> ClaimSchema:
        self.received_context = article_context
        return self.response


def _record() -> ClaimRegistryRecord:
    return ClaimRegistryRecord(
        article_id="A00001",
        sentence_id="3",
        article_published_at=date(2025, 4, 5),
        source_ref="gold_standard_v1",
        claim=ClaimSchema(
            claim_id="A00001_3",
            source_sentence="고용률은 70%였다.",
            indicator="고용률",
            value=70.0,
            unit="%",
            time=None,
            calculation="DIRECT_VALUE",
            parse_status="HOLD",
            parse_reason="MISSING_REQUIRED_SLOTS:time",
        ),
    )


def _response() -> ClaimSchema:
    return ClaimSchema(
        claim_id="model-id",
        source_sentence="model sentence",
        indicator="고용률",
        value=70.0,
        unit="%",
        time="2025년 3월",
        calculation="DIRECT_VALUE",
        parse_status="AUTO_OK",
    )


def test_reparse_sends_only_title_and_bounded_target_neighborhood() -> None:
    extractor = ContextExtractor(_response())
    body = "앞부분" + ("X" * 600) + "고용률은 70%였다." + ("Y" * 600) + "뒷부분"

    records, summary = reparse_records_with_limited_context(
        [_record()],
        extractor,
        {"A00001": {"title": "2025년 3월 고용 동향", "body": body}},
        neighborhood_chars=20,
    )

    assert records[0].claim.time == "2025년 3월"
    assert records[0].source_ref == "gold_standard_v1_openai_context_reparse_v1"
    assert summary["reparsed_auto_ok"] == 1
    assert extractor.received_context is not None
    assert "제목: 2025년 3월 고용 동향" in extractor.received_context
    assert "고용률은 70%였다." in extractor.received_context
    assert "X" * 21 not in extractor.received_context
    assert "Y" * 21 not in extractor.received_context


def test_reparse_holds_when_target_sentence_is_not_in_article_body() -> None:
    records, summary = reparse_records_with_limited_context(
        [_record()],
        ContextExtractor(_response()),
        {"A00001": {"title": "고용 동향", "body": "다른 기사 본문"}},
    )

    assert records[0].claim.parse_status == "HOLD"
    assert records[0].claim.parse_reason == "ARTICLE_CONTEXT_TARGET_NOT_FOUND"
    assert summary["context_unavailable"] == 1
