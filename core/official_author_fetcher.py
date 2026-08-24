"""Direct, auditable retrieval of registered official-author documents."""

from __future__ import annotations

import hashlib
import re
from datetime import date, datetime, timezone
from html import unescape
from time import sleep
from typing import Any, Callable
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from core.kosis_openapi_transport import create_kosis_tls_context
from schemas.claim import ClaimSchema
from schemas.official_author import (
    OfficialAuthorDocumentProfile,
    OfficialAuthorEvidence,
    OfficialAuthorProfile,
)


_TAGS = re.compile(r"<[^>]+>")

def _default_official_opener(request: object, *, timeout: float):
    """Open official Korean public sites with the project's compatible TLS context."""
    return urlopen(request, timeout=timeout, context=create_kosis_tls_context())



class OfficialAuthorDocumentFetcher:
    """Fetch one period-specific official document without search-engine evidence."""

    def __init__(
        self,
        *,
        opener: Callable[..., Any] = _default_official_opener,
        retries: int = 2,
        timeout_seconds: int = 15,
    ) -> None:
        self._opener = opener
        self._retries = max(1, retries)
        self._timeout_seconds = max(1, timeout_seconds)

    def fetch(
        self,
        claim: ClaimSchema,
        profile: OfficialAuthorProfile,
        *,
        article_date: date,
    ) -> OfficialAuthorEvidence:
        document = _select_document(claim.time, profile.documents)
        if document is None:
            return _evidence(profile, status="UNRESOLVED", reason="OFFICIAL_AUTHOR_DOCUMENT_NOT_REGISTERED")
        if not _trusted(document.source_url, profile.trusted_hosts):
            return _evidence(
                profile,
                document=document,
                status="UNRESOLVED",
                reason="OFFICIAL_AUTHOR_HOST_NOT_TRUSTED",
            )
        raw = b""
        for attempt in range(self._retries):
            try:
                request = Request(
                    document.source_url,
                    headers={"Accept": "text/html,application/xhtml+xml", "User-Agent": "CLAFACT-AUTO/0.1"},
                )
                with self._opener(request, timeout=self._timeout_seconds) as response:
                    raw = response.read()
                break
            except (OSError, RuntimeError, TypeError, ValueError):
                if attempt + 1 < self._retries:
                    sleep(2**attempt)
        if not raw:
            return _evidence(
                profile,
                document=document,
                status="FETCH_FAILED",
                reason="OFFICIAL_AUTHOR_FETCH_FAILED",
            )
        content_hash = hashlib.sha256(raw).hexdigest()
        text = _document_text(raw)
        value_match = re.search(document.value_pattern, text, re.IGNORECASE | re.DOTALL)
        published_match = re.search(document.publication_date_pattern, text, re.IGNORECASE)
        period_ok = all(re.search(pattern, text, re.IGNORECASE) for pattern in document.period_patterns)
        published_at = _matched_date(published_match)
        value = _matched_value(value_match, document.scale)
        if not period_ok or published_at is None or value is None:
            return _evidence(
                profile,
                document=document,
                status="UNRESOLVED",
                published_at=published_at,
                value=value,
                content_hash=content_hash,
                reason="OFFICIAL_AUTHOR_DOCUMENT_MISMATCH",
            )
        status = "VERIFIED" if published_at <= article_date else "AS_OF_UNAVAILABLE"
        return _evidence(
            profile,
            document=document,
            status=status,
            published_at=published_at,
            value=value,
            content_hash=content_hash,
            reason=None if status == "VERIFIED" else "AS_OF_UNAVAILABLE",
        )


def _select_document(
    claim_period: str | None, documents: list[OfficialAuthorDocumentProfile]
) -> OfficialAuthorDocumentProfile | None:
    normalized = re.sub(r"[^0-9Q]", "", str(claim_period or "").upper())
    matches = [
        document
        for document in documents
        if re.sub(r"[^0-9Q]", "", document.reference_period.upper()) == normalized
    ]
    return matches[0] if len(matches) == 1 else None


def _trusted(url: str, allowed_hosts: list[str]) -> bool:
    host = (urlparse(url).hostname or "").casefold()
    return any(host == allowed.casefold() or host.endswith("." + allowed.casefold()) for allowed in allowed_hosts)


def _document_text(raw: bytes) -> str:
    text = raw.decode("utf-8", errors="replace")
    return re.sub(r"\s+", " ", unescape(_TAGS.sub(" ", text))).strip()


def _matched_date(match: re.Match[str] | None) -> date | None:
    if match is None:
        return None
    try:
        return date(int(match.group("year")), int(match.group("month")), int(match.group("day")))
    except (IndexError, ValueError):
        return None


def _matched_value(match: re.Match[str] | None, scale: float) -> float | None:
    if match is None:
        return None
    try:
        return float(match.group("value").replace(",", "")) * scale
    except (IndexError, ValueError):
        return None


def _evidence(
    profile: OfficialAuthorProfile,
    *,
    status: str,
    reason: str | None,
    document: OfficialAuthorDocumentProfile | None = None,
    published_at: date | None = None,
    value: float | None = None,
    content_hash: str = "",
) -> OfficialAuthorEvidence:
    return OfficialAuthorEvidence(
        status=status,
        author_name=profile.author_name,
        profile_id=profile.profile_id,
        reference_period=document.reference_period if document else None,
        official_value=value,
        unit=document.unit if document else None,
        published_at=published_at,
        source_url=document.source_url if document else "",
        retrieved_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        content_hash=content_hash,
        reason_code=reason,
    )
