from datetime import date

from core.batch_verifier import BatchArticle
from core.canonical_batch_verifier import verify_articles_with_pipeline
from core.operational_error import OperationalStageError
from core.unified_claim_pipeline import ArticlePipelineResult, PipelineEntry
from schemas.claim import ClaimSchema
from schemas.verdict import VerdictSchema


def _claim(claim_id: str, sentence: str, value: float) -> ClaimSchema:
    return ClaimSchema(
        claim_id=claim_id,
        source_sentence=sentence,
        indicator="고용률",
        value=value,
        unit="%",
        time="2024년",
        frequency="년",
        calculation="DIRECT_VALUE",
        parse_status="AUTO_OK",
    )


def _resolution(claim: ClaimSchema):
    verdict = VerdictSchema(
        claim_id=claim.claim_id,
        claim_value=claim.value,
        evidence_values=[claim.value],
        calculated_value=claim.value,
        verdict="MATCH",
        route_status="AUTO",
        reason_code="WITHIN_TOLERANCE",
        explanation="matched",
        dataset_version="test",
        semantic_standard_version="test",
        kosis_catalog_version="test",
        matching_version="test",
        calculation_version="test",
    )
    return type("Resolution", (), {"verdict": verdict})()


class _Runtime:
    def verify_article(self, article_text, *, article_published_at, article_id=None):
        first = _claim("child-1", "2023년 고용률은 60%", 60)
        second = _claim("child-2", "2024년 고용률은 61%였다.", 61)
        return ArticlePipelineResult(
            article_id=article_id,
            entries=[
                PipelineEntry("parent", first, "MULTI_CLAIM_SPLIT", "KOSIS_PIPELINE_ELIGIBLE", "AUTO", "WITHIN_TOLERANCE", _resolution(first)),
                PipelineEntry("parent", second, "MULTI_CLAIM_SPLIT", "KOSIS_PIPELINE_ELIGIBLE", "AUTO", "WITHIN_TOLERANCE", _resolution(second)),
            ],
        )


def test_canonical_batch_flattens_all_pipeline_entries() -> None:
    article = BatchArticle(
        "A1",
        date(2025, 4, 9),
        "2023년 고용률은 60%였고 2024년 고용률은 61%였다.",
    )

    result = verify_articles_with_pipeline([article], _Runtime())

    assert [row.claim_id for row in result.claim_rows] == ["child-1", "child-2"]
    assert [row.claim_value for row in result.claim_rows] == [60, 61]
    assert result.article_rows[0].claim_count == 2
    assert result.article_rows[0].article_status == "ALL_MATCH"


def test_canonical_batch_preserves_stable_reason_and_separate_diagnostic() -> None:
    class FailingRuntime:
        def verify_article(self, article_text, *, article_published_at, article_id=None):
            raise OperationalStageError("CLAIM_PARSE", "diag12345678")

    article = BatchArticle(
        "A1", date(2025, 4, 9), "2024년 고용률은 61%였다."
    )

    result = verify_articles_with_pipeline([article], FailingRuntime())

    assert result.claim_rows[0].reason_code == "CLAIM_PARSE_UNAVAILABLE"
    assert result.claim_rows[0].diagnostic_id == "diag12345678"
