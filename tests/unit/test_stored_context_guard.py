from datetime import date

from core.unified_claim_pipeline import verify_registry_record
from schemas.claim import ClaimSchema
from schemas.claim_registry import ClaimRegistryRecord


class _NoExtractor:
    pass


class _ForbiddenOfficialService:
    def resolve(self, claim, *, article_date):
        raise AssertionError("context-dependent Claim must not reach official lookup")


def test_stored_continuation_claim_without_article_context_is_held_before_lookup() -> None:
    source = "고용률도 2011년 36.8%에서 지난달 48.3%로 불었다."
    expression = "36.8%"
    start = source.index(expression)
    claim = ClaimSchema(
        claim_id="context-rate",
        source_sentence=source,
        indicator="고용률",
        value=36.8,
        unit="%",
        time="2011",
        frequency="Y",
        calculation="DIRECT_VALUE",
        parse_status="AUTO_OK",
    )
    record = ClaimRegistryRecord(
        article_id="A1",
        sentence_id="1",
        article_published_at=date(2025, 6, 12),
        source_ref="fixture",
        claim=claim,
        slot_enrichment={
            "target_link_status": "SOURCE_GROUNDED",
            "target_numeric_expression": expression,
            "target_numeric_start": start,
            "target_numeric_end": start + len(expression),
        },
    )

    entries = verify_registry_record(
        record,
        extractor=_NoExtractor(),
        official_service=_ForbiddenOfficialService(),
        article_context=None,
        allow_structured_recovery=False,
    )

    assert len(entries) == 1
    assert entries[0].terminal_status == "HUMAN_REVIEW"
    assert entries[0].reason_code == "CONTEXT_TARGET_UNRESOLVED"
