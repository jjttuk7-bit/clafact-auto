from io import BytesIO
from urllib.error import URLError

import pytest

from core.article_source_fetcher import (
    ArticleSourceFetchError,
    ArticleSourceFetcher,
)


class _Response:
    def __init__(self, text: str) -> None:
        self._stream = BytesIO(text.encode("utf-8"))

    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return self._stream.read()


def test_fetch_reads_source_via_reader_and_keeps_only_markdown_content() -> None:
    seen_url: str | None = None

    def transport(request, *, timeout: int):
        nonlocal seen_url
        seen_url = request.full_url
        assert timeout == 20
        return _Response(
            "Title: 기사 제목\n\nURL Source: https://example.test/a\n\n"
            "Markdown Content:\n본문 첫 문장.\n대상 문장은 70%였다."
        )

    article = ArticleSourceFetcher(transport=transport).fetch("https://example.test/a")

    assert seen_url == "https://r.jina.ai/https://example.test/a"
    assert article.source_url == "https://example.test/a"
    assert article.body == "본문 첫 문장.\n대상 문장은 70%였다."
    assert len(article.content_sha256) == 64


def test_fetch_raises_stable_error_when_reader_is_unavailable() -> None:
    def transport(_request, *, timeout: int):
        raise URLError("offline")

    with pytest.raises(ArticleSourceFetchError, match="ARTICLE_SOURCE_FETCH_FAILED"):
        ArticleSourceFetcher(transport=transport).fetch("https://example.test/a")
