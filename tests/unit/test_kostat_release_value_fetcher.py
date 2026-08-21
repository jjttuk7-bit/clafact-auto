from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import date

import pytest

from core.kostat_release_value_fetcher import (
    KostatReleaseDocument,
    KostatReleaseDocumentFetcher,
    extract_unambiguous_release_value,
)


class Response:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self) -> bytes:
        return self._payload


def test_follows_official_pdf_attachment_and_preserves_document_digest() -> None:
    release_url = "https://www.kostat.go.kr/board.es?bid=229&act=view&list_no=438232"
    pdf_url = "https://www.kostat.go.kr/boardDownload.es?bid=229&list_no=438232&seq=3"
    release_page = (
        '<h1>2025년 재배면적조사 결과</h1><p>게시일 2025-08-28</p>'
        '<a href="/boardDownload.es?bid=229&list_no=438232&seq=3">첨부 PDF</a>'
    ).encode()
    pdf = b"%PDF-1.4 official release"

    def opener(request, *, timeout):
        return Response(pdf if request.full_url == pdf_url else release_page)

    evidence = KostatReleaseDocumentFetcher(opener=opener).fetch_document(
        release_url=release_url, article_date=date(2025, 10, 2)
    )

    assert evidence is not None
    assert evidence.published_at == date(2025, 8, 28)
    assert evidence.release_url == release_url
    assert evidence.source_url == pdf_url
    assert evidence.retrieved_at.endswith("Z")
    assert evidence.document_hash == "sha256:" + hashlib.sha256(pdf).hexdigest()


def test_rejects_release_published_after_article_date() -> None:
    release_url = "https://www.kostat.go.kr/board.es?bid=229&act=view&list_no=438232"
    release_page = "<p>게시일 2025-10-03</p>".encode()

    evidence = KostatReleaseDocumentFetcher(
        opener=lambda *_args, **_kwargs: Response(release_page)
    ).fetch_document(release_url=release_url, article_date=date(2025, 10, 2))

    assert evidence is None


def test_rejects_non_https_or_non_kostat_release_urls() -> None:
    fetcher = KostatReleaseDocumentFetcher(opener=lambda *_args, **_kwargs: pytest.fail("must not fetch"))

    assert fetcher.fetch_document(
        release_url="http://www.kostat.go.kr/board.es?bid=229", article_date=date(2025, 10, 2)
    ) is None
    assert fetcher.fetch_document(
        release_url="https://example.com/release.pdf", article_date=date(2025, 10, 2)
    ) is None



def test_does_not_fetch_http_or_non_kostat_pdf_attachment() -> None:
    release_url = "https://www.kostat.go.kr/board.es?bid=229&act=view&list_no=438232"
    release_page = (
        '<p>게시일 2025-08-28</p>'
        '<a href="http://www.kostat.go.kr/boardDownload.es?seq=3">unsafe</a>'
        '<a href="https://example.com/official.pdf">unsafe</a>'
    ).encode()
    requested: list[str] = []

    def opener(request, *, timeout):
        requested.append(request.full_url)
        return Response(release_page)

    evidence = KostatReleaseDocumentFetcher(opener=opener).fetch_document(
        release_url=release_url, article_date=date(2025, 10, 2)
    )

    assert evidence is None
    assert requested == [release_url]


def test_rejects_non_pdf_attachment_response() -> None:
    release_url = "https://www.kostat.go.kr/board.es?bid=229&act=view&list_no=438232"
    pdf_url = "https://www.kostat.go.kr/boardDownload.es?bid=229&list_no=438232&seq=3"
    release_page = (
        '<p>게시일 2025-08-28</p>'
        '<a href="/boardDownload.es?bid=229&list_no=438232&seq=3">첨부</a>'
    ).encode()

    def opener(request, *, timeout):
        return Response(b"<html>login page</html>" if request.full_url == pdf_url else release_page)

    evidence = KostatReleaseDocumentFetcher(opener=opener).fetch_document(
        release_url=release_url, article_date=date(2025, 10, 2)
    )

    assert evidence is None


@pytest.mark.parametrize(
    "release_page",
    [
        "<p>공표일이 없습니다.</p>",
        "<p>게시일 2025-08-28</p><p>공표일 2025-08-29</p>",
        "<p>게시일 2025-02-30</p>",
    ],
)
def test_rejects_missing_ambiguous_or_invalid_publication_date(release_page: str) -> None:
    release_url = "https://www.kostat.go.kr/board.es?bid=229&act=view&list_no=438232"

    evidence = KostatReleaseDocumentFetcher(
        opener=lambda *_args, **_kwargs: Response(release_page.encode())
    ).fetch_document(release_url=release_url, article_date=date(2025, 10, 2))

    assert evidence is None




def _release_document() -> KostatReleaseDocument:
    return KostatReleaseDocument(
        release_url="https://www.kostat.go.kr/board.es?bid=229&act=view&list_no=438232",
        source_url="https://www.kostat.go.kr/boardDownload.es?bid=229&list_no=438232&seq=3",
        published_at=date(2025, 8, 28),
        document_hash="sha256:" + hashlib.sha256(b"%PDF-1.4 fixture").hexdigest(),
        retrieved_at="2025-08-28T00:00:00Z",
        document_bytes=b"%PDF-1.4 fixture",
    )


def test_extracts_one_explicit_period_indicator_and_unit_matched_value() -> None:
    value = extract_unambiguous_release_value(
        _release_document(),
        period="2025",
        indicator="\ubcbc \uc7ac\ubc30\uba74\uc801",
        unit="ha",
        claim_scope="\ub300\ud55c\ubbfc\uad6d",
        document_scope="\uc804\uad6d",
        pdf_text_extractor=lambda _raw: "2025\ub144 \ubcbc \uc7ac\ubc30\uba74\uc801\uc740 677,597ha\ub85c \uc870\uc0ac\ub418\uc5c8\ub2e4.",
    )

    assert value == 677_597.0


@pytest.mark.parametrize(
    ("text", "period", "indicator", "unit"),
    [
        ("2024\ub144 \ubcbc \uc7ac\ubc30\uba74\uc801\uc740 677,597ha\uc774\ub2e4.", "2025", "\ubcbc \uc7ac\ubc30\uba74\uc801", "ha"),
        ("2025\ub144 \ucf69 \uc7ac\ubc30\uba74\uc801\uc740 677,597ha\uc774\ub2e4.", "2025", "\ubcbc \uc7ac\ubc30\uba74\uc801", "ha"),
        ("2025\ub144 \ubcbc \uc7ac\ubc30\uba74\uc801\uc740 677,597\ud3c9\uc774\ub2e4.", "2025", "\ubcbc \uc7ac\ubc30\uba74\uc801", "ha"),
        ("2025\ub144 \ubcbc \uc7ac\ubc30\uba74\uc801\uc740 677,597ha\uc774\ub2e4.", "2025", "\ubcbc \uc7ac\ubc30\uba74\uc801", "%"),
    ],
)
def test_rejects_missing_or_incompatible_scope(
    text: str, period: str, indicator: str, unit: str
) -> None:
    assert (
        extract_unambiguous_release_value(
            _release_document(),
            period=period,
            indicator=indicator,
            unit=unit,
            pdf_text_extractor=lambda _raw: text,
        )
        is None
    )


@pytest.mark.parametrize(
    "text",
    [
        (
            "2025\ub144 \ubcbc \uc7ac\ubc30\uba74\uc801\uc740 677,597ha\uc774\ub2e4. "
            "2025\ub144 \ubcbc \uc7ac\ubc30\uba74\uc801\uc740 677,713ha\uc774\ub2e4."
        ),
        "2025\ub144 \ubcbc \uc7ac\ubc30\uba74\uc801\uc740 \uc804\ub144\ubcf4\ub2e4 2.9% \uac10\uc18c\ud558\uc600\ub2e4.",
        "2025\ub144 \ubcbc \uc7ac\ubc30\uba74\uc801\uc740 2\ub9ccha \uac10\uc18c\ud558\uc600\ub2e4.",
    ],
)
def test_rejects_conflicting_or_calculation_only_statements(text: str) -> None:
    calls: list[bytes] = []

    def extractor(raw: bytes) -> str:
        calls.append(raw)
        return text

    assert (
        extract_unambiguous_release_value(
            _release_document(),
            period="2025",
            indicator="\ubcbc \uc7ac\ubc30\uba74\uc801",
            unit="ha",
            claim_scope="\ub300\ud55c\ubbfc\uad6d",
            document_scope="\uc804\uad6d",
            pdf_text_extractor=extractor,
        )
        is None
    )
    assert calls == [b"%PDF-1.4 fixture"]

@pytest.mark.parametrize(
    "document_scope",
    ["\ubd81\ud55c", "\uc804\ub77c\ub0a8\ub3c4"],
)
def test_rejects_document_scope_mismatched_to_national_claim(document_scope: str) -> None:
    assert (
        extract_unambiguous_release_value(
            _release_document(),
            period="2025",
            indicator="\ubcbc \uc7ac\ubc30\uba74\uc801",
            unit="ha",
            claim_scope="\ub300\ud55c\ubbfc\uad6d",
            document_scope=document_scope,
            pdf_text_extractor=lambda _raw: "2025\ub144 \ubcbc \uc7ac\ubc30\uba74\uc801\uc740 677,597ha\uc774\ub2e4.",
        )
        is None
    )


def test_rejects_missing_document_scope() -> None:
    assert (
        extract_unambiguous_release_value(
            _release_document(),
            period="2025",
            indicator="\ubcbc \uc7ac\ubc30\uba74\uc801",
            unit="ha",
            claim_scope="\ub300\ud55c\ubbfc\uad6d",
            document_scope=None,
            pdf_text_extractor=lambda _raw: "2025\ub144 \ubcbc \uc7ac\ubc30\uba74\uc801\uc740 677,597ha\uc774\ub2e4.",
        )
        is None
    )


@pytest.mark.parametrize(
    "document",
    [
        replace(_release_document(), document_hash="sha256:" + "0" * 64),
        replace(_release_document(), document_bytes=b"not a PDF"),
    ],
)
def test_public_extractor_rejects_tampered_or_non_pdf_document(
    document: KostatReleaseDocument,
) -> None:
    assert (
        extract_unambiguous_release_value(
            document,
            period="2025",
            indicator="\ubcbc \uc7ac\ubc30\uba74\uc801",
            unit="ha",
            claim_scope="\ub300\ud55c\ubbfc\uad6d",
            document_scope="\uc804\uad6d",
            pdf_text_extractor=lambda _raw: "2025\ub144 \ubcbc \uc7ac\ubc30\uba74\uc801\uc740 677,597ha\uc774\ub2e4.",
        )
        is None
    )

def test_selects_pdf_attachment_after_non_pdf_board_download_links() -> None:
    from core.kostat_release_value_fetcher import _official_pdf_attachment_url

    release_url = "https://www.kostat.go.kr/board.es?bid=229&act=view&list_no=438232"
    page = (
        '<a href="/boardDownload.es?bid=229&list_no=438232&seq=1">첨부자료.hwp</a>'
        '<a href="/boardDownload.es?bid=229&list_no=438232&seq=3">첨부자료.pdf</a>'
    ).encode()

    assert _official_pdf_attachment_url(page, release_url) == (
        "https://www.kostat.go.kr/boardDownload.es?bid=229&list_no=438232&seq=3"
    )