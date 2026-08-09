from datetime import date
from io import BytesIO

from openpyxl import load_workbook

import pytest

from core.batch_verifier import (
    BatchArticle,
    BatchClaimResult,
    export_batch_xlsx,
    load_articles,
    verify_articles,
)
from schemas.verdict import VerdictSchema


def _match_verdict(claim_id: str = "claim-1") -> VerdictSchema:
    return VerdictSchema(
        claim_id=claim_id,
        claim_value=28589000,
        evidence_values=[28589.0],
        calculated_value=28589000,
        verdict="MATCH",
        route_status="AUTO",
        reason_code="WITHIN_TOLERANCE",
        explanation="Claim matches the official calculation.",
        dataset_version="test",
        semantic_standard_version="test",
        kosis_catalog_version="test",
        matching_version="test",
        calculation_version="test",
    )


def test_load_articles_requires_required_columns() -> None:
    with pytest.raises(ValueError, match="BATCH_REQUIRED_COLUMNS"):
        load_articles("articles.csv", b"article_id,published_at\nA1,2025-04-09\n")


def test_load_articles_reads_csv_without_persisting_upload() -> None:
    articles = load_articles(
        "articles.csv",
        "article_id,published_at,title,body,source_url\nA1,2025-04-09,employment,2025년 3월 취업자 수는 2858만9000명이었다.,https://example.test/a1\n".encode(),
    )

    assert articles == [
        BatchArticle(
            article_id="A1",
            published_at=date(2025, 4, 9),
            body="2025년 3월 취업자 수는 2858만9000명이었다.",
            title="employment",
            source_url="https://example.test/a1",
        )
    ]


def test_verify_articles_creates_one_claim_result_per_numeric_sentence() -> None:
    article = BatchArticle("A1", date(2025, 4, 9), "배경이다. 2025년 3월 취업자 수는 2858만9000명이었다.")
    result = verify_articles([article], lambda sentence, _: _match_verdict())

    assert len(result.claim_rows) == 1
    assert result.claim_rows[0].article_id == "A1"
    assert result.claim_rows[0].source_sentence == "2025년 3월 취업자 수는 2858만9000명이었다."
    assert result.article_rows[0].article_status == "ALL_MATCH"


def test_verify_articles_converts_verifier_failure_to_hold() -> None:
    article = BatchArticle("A1", date(2025, 4, 9), "2025년 3월 취업자 수는 2858만9000명이었다.")
    result = verify_articles([article], lambda sentence, _: (_ for _ in ()).throw(RuntimeError("failure")))

    assert result.claim_rows[0].route_status == "HOLD"
    assert result.claim_rows[0].reason_code == "BATCH_VERIFIER_ERROR"


def test_export_batch_xlsx_has_claim_summary_and_review_sheets() -> None:
    result = verify_articles(
        [BatchArticle("A1", date(2025, 4, 9), "2025년 3월 취업자 수는 2858만9000명이었다.")],
        lambda sentence, _: _match_verdict(),
    )

    payload = export_batch_xlsx(result)

    assert payload[:2] == b"PK"
    assert load_workbook(BytesIO(payload)).sheetnames == ["Claim Results", "Article Summary", "Review Queue"]


def test_load_articles_accepts_sentence_level_crawler_columns_with_default_date() -> None:
    articles = load_articles(
        "crawler.csv",
        "article_id,sentence_id,sentence,source_type\nA00006,1,2024년 수출은 6838억 달러였다.,KOSIS\n".encode(),
        default_published_at=date(2025, 4, 9),
    )

    assert articles[0].article_id == "A00006"
    assert articles[0].body == "2024년 수출은 6838억 달러였다."
    assert articles[0].published_at == date(2025, 4, 9)


def test_load_articles_requires_date_when_sentence_file_has_no_article_date() -> None:
    with pytest.raises(ValueError, match="BATCH_ARTICLE_DATE_REQUIRED"):
        load_articles("crawler.csv", b"article_id,sentence\nA00006,2024 data\n")
