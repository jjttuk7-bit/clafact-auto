"""Batch adapter for the canonical article pipeline."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol

from core.batch_verifier import (
    BatchArticle,
    BatchClaimResult,
    BatchVerificationResult,
    _claim_row,
    _hold_row,
    _summaries,
)
from core.operational_error import OperationalStageError
from core.unified_claim_pipeline import ArticlePipelineResult, PipelineEntry


class ArticlePipelineRuntime(Protocol):
    def verify_article(self, article_text: str, *, article_published_at, article_id: str | None = None) -> ArticlePipelineResult: ...


def verify_articles_with_pipeline(
    articles: Iterable[BatchArticle],
    runtime: ArticlePipelineRuntime,
) -> BatchVerificationResult:
    """Verify each article once and flatten every canonical child Claim."""
    materialized = list(articles)
    rows: list[BatchClaimResult] = []
    for article in materialized:
        try:
            result = runtime.verify_article(
                article.body,
                article_published_at=article.published_at,
                article_id=article.article_id,
            )
        except OperationalStageError as error:
            rows.append(_hold_row(
                article,
                article.body,
                f"{error.stage}_UNAVAILABLE",
                diagnostic_id=error.diagnostic_id,
            ))
            continue
        except Exception:
            rows.append(_hold_row(article, article.body))
            continue
        rows.extend(_entry_row(article, entry) for entry in result.entries)
    return BatchVerificationResult(rows, _summaries(materialized, rows))


def _entry_row(article: BatchArticle, entry: PipelineEntry) -> BatchClaimResult:
    resolution = entry.official_resolution
    verdict = getattr(resolution, "verdict", None) if resolution is not None else None
    if verdict is not None:
        return _claim_row(article, entry.claim.source_sentence, verdict)
    return BatchClaimResult(
        article_id=article.article_id,
        published_at=article.published_at,
        source_sentence=entry.claim.source_sentence,
        claim_id=entry.claim.claim_id,
        verdict="UNDETERMINED",
        route_status=entry.terminal_status,
        reason_code=entry.reason_code or entry.admission_route,
        claim_value=entry.claim.value,
        calculated_value=None,
        evidence_value=None,
        kosis_table_id=None,
        evidence_key=None,
        source_url=article.source_url,
    )
