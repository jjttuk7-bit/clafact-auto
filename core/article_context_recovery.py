"""Batch recovery of article context with immutable source provenance."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol
from dataclasses import dataclass

from core.article_source_fetcher import FetchedArticle


@dataclass(frozen=True)
class ArticleContextSource:
    article_id: str
    title: str
    article_published_at: str
    source_url: str


class ArticleFetcher(Protocol):
    def fetch(self, source_url: str) -> FetchedArticle: ...


def recover_article_contexts(
    sources: Iterable[ArticleContextSource],
    fetcher: ArticleFetcher,
) -> tuple[list[dict[str, str]], dict[str, int]]:
    """Recover source text while recording a stable result for every requested URL."""
    output: list[dict[str, str]] = []
    requested = 0
    failed = 0
    for source in sources:
        requested += 1
        try:
            article = fetcher.fetch(source.source_url)
        except Exception:
            failed += 1
            continue
        output.append(
            {
                "article_id": source.article_id,
                "title": source.title,
                "article_published_at": source.article_published_at,
                "url": source.source_url,
                "body": article.body,
                "content_sha256": article.content_sha256,
                "reader_url": article.reader_url,
                "fetched_at": article.fetched_at.isoformat(),
            }
        )
    return output, {"requested": requested, "recovered": len(output), "failed": failed}


