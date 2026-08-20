from datetime import datetime, timezone

from core.article_context_recovery import ArticleContextSource, recover_article_contexts
from core.article_source_fetcher import FetchedArticle


class FakeFetcher:
    def fetch(self, source_url: str) -> FetchedArticle:
        return FetchedArticle(
            source_url=source_url,
            reader_url=f"https://r.jina.ai/{source_url}",
            body="복구된 원문 본문",
            content_sha256="a" * 64,
            fetched_at=datetime(2026, 8, 20, tzinfo=timezone.utc),
        )


def test_recovery_preserves_article_identity_and_fetch_provenance() -> None:
    contexts, report = recover_article_contexts(
        [
            ArticleContextSource(
                article_id="A00001",
                title="기사 제목",
                article_published_at="2025-04-01",
                source_url="https://example.test/a",
            )
        ],
        FakeFetcher(),
    )

    assert contexts == [
        {
            "article_id": "A00001",
            "title": "기사 제목",
            "article_published_at": "2025-04-01",
            "url": "https://example.test/a",
            "body": "복구된 원문 본문",
            "content_sha256": "a" * 64,
            "reader_url": "https://r.jina.ai/https://example.test/a",
            "fetched_at": "2026-08-20T00:00:00+00:00",
        }
    ]
    assert report == {"requested": 1, "recovered": 1, "failed": 0}
