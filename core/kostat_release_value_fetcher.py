"""Dependency-injected retrieval of auditable Statistics Korea release documents.

This module intentionally retrieves release provenance only.  It neither
extracts a numeric value nor decides a verdict; those are later deterministic
pipeline responsibilities.
"""

from __future__ import annotations

import hashlib
from io import BytesIO
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from html import unescape
from typing import Any, Callable, Protocol
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

from core.kosis_publication import extract_official_release_value
from schemas.claim import ClaimSchema


class KostatReleaseValueFetcher(Protocol):
    """Interface selected by the official-author registry.

    Implementations directly query Statistics Korea only after the KOSIS-first
    pipeline has performed its official lookup attempt.
    """

    def find_release(
        self,
        *,
        claim: ClaimSchema,
        indicator_search_terms: tuple[str, ...],
        article_date: date,
    ) -> object | None:
        """Return release evidence, or ``None`` when no release is usable."""


class KostatReleaseDocumentRetriever(Protocol):
    """Retrieve a previously discovered KOSTAT release page and its document."""

    def fetch_document(
        self, *, release_url: str, article_date: date
    ) -> "KostatReleaseDocument | None":
        """Return only an official document published no later than the article."""


@dataclass(frozen=True, slots=True)
class KostatReleaseDocument:
    """Value-free provenance for a document attached to a KOSTAT release."""

    release_url: str
    source_url: str
    published_at: date
    document_hash: str
    retrieved_at: str
    document_bytes: bytes


_DEFAULT_TIMEOUT_SECONDS = 10
_DATE = re.compile(
    r"(?:게시일|보도시점|공표일자)\s*[:：]?\s*"
    r"(?P<year>20\d{2})\s*(?:-|\.|년\s*)\s*"
    r"(?P<month>0?[1-9]|1[0-2])(?:-|\.|월\s*)\s*"
    r"(?P<day>0?[1-9]|[12]\d|3[01])(?!\d)\s*(?:일)?"
)
_HREF = re.compile(r"href=[\"'](?P<href>[^\"']+)[\"']", re.IGNORECASE)
_ATTACHMENT_LINK = re.compile(
    r"<a[^>]*href=[\"'](?P<href>[^\"']+)[\"'][^>]*>(?P<label>.*?)</a>",
    re.IGNORECASE | re.DOTALL,
)


def _default_opener(request: object, *, timeout: float):
    return urlopen(request, timeout=timeout)


class KostatReleaseDocumentFetcher:
    """Fetch a KOSTAT release attachment through an injected HTTP transport."""

    def __init__(
        self,
        *,
        opener: Callable[..., Any] = _default_opener,
        timeout_seconds: int = _DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._opener = opener
        self._timeout_seconds = max(1, timeout_seconds)

    def fetch_document(
        self, *, release_url: str, article_date: date
    ) -> KostatReleaseDocument | None:
        """Follow one official PDF attachment after validating its release date."""
        if not _is_official_kostat_url(release_url):
            return None
        release_bytes = self._fetch(release_url, accept="text/html")
        if release_bytes is None:
            return None
        published_at = _published_at(release_bytes)
        if published_at is None or published_at > article_date:
            return None
        document_url = _official_pdf_attachment_url(release_bytes, release_url)
        if document_url is None:
            return None
        document_bytes = self._fetch(document_url, accept="application/pdf")
        if document_bytes is None or not document_bytes.startswith(b"%PDF-"):
            return None
        return KostatReleaseDocument(
            release_url=release_url,
            source_url=document_url,
            published_at=published_at,
            document_hash="sha256:" + hashlib.sha256(document_bytes).hexdigest(),
            retrieved_at=_now(),
            document_bytes=document_bytes,
        )

    def _fetch(self, url: str, *, accept: str) -> bytes | None:
        try:
            request = Request(
                url,
                headers={
                    "Accept": accept,
                    "User-Agent": "Mozilla/5.0 (compatible; CLAFACT-AUTO/0.1)",
                },
            )
            with self._opener(request, timeout=self._timeout_seconds) as response:
                return response.read()
        except (OSError, RuntimeError, TypeError, ValueError):
            return None


def _is_official_kostat_url(url: str) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or "").casefold()
    return parsed.scheme == "https" and (host == "kostat.go.kr" or host.endswith(".kostat.go.kr"))


def _published_at(raw: bytes) -> date | None:
    text = unescape(re.sub(r"<[^>]+>", " ", raw.decode("utf-8", errors="replace")))
    matches = list(_DATE.finditer(text))
    if len(matches) != 1:
        return None
    match = matches[0]
    try:
        return date(int(match.group("year")), int(match.group("month")), int(match.group("day")))
    except ValueError:
        return None


def _official_pdf_attachment_url(raw: bytes, release_url: str) -> str | None:
    page = raw.decode("utf-8", errors="replace")
    for match in _ATTACHMENT_LINK.finditer(page):
        candidate = urljoin(release_url, unescape(match.group("href")))
        label = re.sub(r"<[^>]+>", " ", unescape(match.group("label"))).strip().casefold()
        path = urlparse(candidate).path.casefold()
        if not (path.endswith(".pdf") or "boarddownload" in path):
            continue
        # boardDownload URLs do not include an extension; accept them only when
        # their visible, official attachment name explicitly identifies a PDF.
        if "boarddownload" in path and ".pdf" not in label and "pdf" not in label:
            continue
        if _is_official_kostat_url(candidate):
            return candidate
    return None

def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")




def extract_unambiguous_release_value(
    document: KostatReleaseDocument,
    *,
    period: str,
    indicator: str,
    unit: str,
    claim_scope: str | None = None,
    document_scope: str | None = None,
    pdf_text_extractor: Callable[[bytes], str | None] | None = None,
) -> float | None:
    """Return one explicit official value from a verified KOSTAT PDF, or ``None``.

    This function deliberately performs no derivation: a value is accepted only
    when the release text itself explicitly binds one unique number to the
    requested period, indicator, and compatible unit.
    """
    if not _is_verified_official_document(document) or not _scope_matches(claim_scope, document_scope):
        return None
    extractor = pdf_text_extractor or _extract_pdf_text
    try:
        text = extractor(document.document_bytes)
    except (OSError, RuntimeError, TypeError, ValueError):
        return None
    if not text or not text.strip():
        return None
    return extract_official_release_value(
        text, period=period, indicator=indicator, unit=unit
    )


def _is_verified_official_document(document: KostatReleaseDocument) -> bool:
    if not (
        _is_official_kostat_url(document.release_url)
        and _is_official_kostat_url(document.source_url)
        and document.document_bytes.startswith(b"%PDF-")
    ):
        return False
    expected_hash = "sha256:" + hashlib.sha256(document.document_bytes).hexdigest()
    return document.document_hash == expected_hash


def _extract_pdf_text(raw: bytes) -> str | None:
    """Read textual PDF content without OCR or numeric inference."""
    try:
        from pypdf import PdfReader

        reader = PdfReader(BytesIO(raw))
        pages = [page.extract_text() or "" for page in reader.pages]
    except (ImportError, OSError, RuntimeError, TypeError, ValueError):
        return None
    text = "\n".join(pages).strip()
    return text or None

_NATIONAL_SCOPE = frozenset(
    {"\uc804\uad6d", "\ub300\ud55c\ubbfc\uad6d", "\ud55c\uad6d", "national"}
)
_SCOPE_ALIASES = {
    "\uc804\ub0a8": "\uc804\ub77c\ub0a8\ub3c4",
    "\uc804\ubd81": "\uc804\ub77c\ubd81\ub3c4",
    "\uacbd\ub0a8": "\uacbd\uc0c1\ub0a8\ub3c4",
    "\uacbd\ubd81": "\uacbd\uc0c1\ubd81\ub3c4",
    "\ucda9\ub0a8": "\ucda9\uccad\ub0a8\ub3c4",
    "\ucda9\ubd81": "\ucda9\uccad\ubd81\ub3c4",
}


def _scope_matches(claim_scope: str | None, document_scope: str | None) -> bool:
    """Require an explicit, same-scope claim/document pairing.

    A national claim cannot use a North Korean or provincial release.  Local
    claims are accepted only for their exact canonical administrative scope.
    """
    claim = _canonical_scope(claim_scope)
    document = _canonical_scope(document_scope)
    if not claim or not document:
        return False
    if claim in _NATIONAL_SCOPE:
        return document in _NATIONAL_SCOPE
    return claim == document


def _canonical_scope(scope: str | None) -> str | None:
    normalized = re.sub(r"\s+", "", scope or "").casefold()
    if not normalized:
        return None
    if normalized in _NATIONAL_SCOPE:
        return "national"
    return _SCOPE_ALIASES.get(normalized, normalized)