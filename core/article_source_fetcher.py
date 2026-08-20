"""Read-only article-source adapter for recoverable local context storage."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


JINA_READER_PREFIX = "https://r.jina.ai/"
ARTICLE_SOURCE_TIMEOUT_SECONDS = 20
Transport = Callable[..., Any]


class ArticleSourceFetchError(RuntimeError):
    """Raised when a source article cannot be retrieved as usable text."""


@dataclass(frozen=True)
class FetchedArticle:
    source_url: str
    reader_url: str
    body: str
    content_sha256: str
    fetched_at: datetime


class ArticleSourceFetcher:
    """Fetch article text through a reader endpoint without mutating source data."""

    def __init__(self, transport: Transport | None = None) -> None:
        self._transport = transport or urlopen

    def fetch(self, source_url: str) -> FetchedArticle:
        _validate_source_url(source_url)
        reader_url = f"{JINA_READER_PREFIX}{source_url}"
        request = Request(reader_url, headers={"User-Agent": "CLAFACT-AUTO/0.1"})
        try:
            with self._transport(request, timeout=ARTICLE_SOURCE_TIMEOUT_SECONDS) as response:
                payload = response.read()
        except (HTTPError, URLError, TimeoutError, OSError):
            raise ArticleSourceFetchError("ARTICLE_SOURCE_FETCH_FAILED") from None

        try:
            text = payload.decode("utf-8")
        except UnicodeDecodeError:
            raise ArticleSourceFetchError("ARTICLE_SOURCE_INVALID_ENCODING") from None
        body = _markdown_content(text)
        if not body:
            raise ArticleSourceFetchError("ARTICLE_SOURCE_CONTENT_UNAVAILABLE")
        return FetchedArticle(
            source_url=source_url,
            reader_url=reader_url,
            body=body,
            content_sha256=sha256(body.encode("utf-8")).hexdigest(),
            fetched_at=datetime.now(timezone.utc),
        )


def _validate_source_url(source_url: str) -> None:
    parsed = urlparse(source_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("source_url must be an absolute http(s) URL")


def _markdown_content(reader_response: str) -> str:
    marker = "Markdown Content:"
    _prefix, found, content = reader_response.partition(marker)
    if not found:
        return ""
    return content.strip()
