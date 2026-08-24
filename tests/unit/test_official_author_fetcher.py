from datetime import date

from core.official_author_fetcher import OfficialAuthorDocumentFetcher
from schemas.claim import ClaimSchema
from schemas.official_author import OfficialAuthorDocumentProfile, OfficialAuthorProfile


class _Response:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self) -> bytes:
        return self._body


def _claim() -> ClaimSchema:
    return ClaimSchema(
        claim_id="c1",
        source_sentence="2024년 미국 라면 수출 증가율은 70.3%였다.",
        indicator="대미 라면 수출 증가율",
        value=70.3,
        unit="%",
        time="2024",
        calculation="GROWTH_RATE",
        parse_status="AUTO_OK",
    )


def _profile(url: str = "https://official.go.kr/release/1") -> OfficialAuthorProfile:
    return OfficialAuthorProfile(
        profile_id="food",
        author_name="공식기관",
        indicator_terms=["라면", "수출"],
        trusted_hosts=["official.go.kr"],
        documents=[OfficialAuthorDocumentProfile(
            reference_period="2024",
            source_url=url,
            value_pattern=r"미국 라면 수출 증가율은 (?P<value>\d+(?:\.\d+)?)%",
            period_patterns=["2024년"],
            unit="%",
            publication_date_pattern=r"게시일\s*(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})",
        )],
    )


def test_fetches_official_document_and_preserves_audit_fields() -> None:
    raw = "<html>게시일 2025-01-02 2024년 미국 라면 수출 증가율은 70.3%</html>".encode()
    fetcher = OfficialAuthorDocumentFetcher(opener=lambda *_args, **_kwargs: _Response(raw))

    evidence = fetcher.fetch(_claim(), _profile(), article_date=date(2025, 1, 4))

    assert evidence.status == "VERIFIED"
    assert evidence.official_value == 70.3
    assert evidence.unit == "%"
    assert evidence.published_at == date(2025, 1, 2)
    assert evidence.source_url == "https://official.go.kr/release/1"
    assert len(evidence.content_hash) == 64
    assert evidence.retrieved_at.endswith("Z")


def test_rejects_untrusted_host_without_requesting_it() -> None:
    attempts = 0

    def opener(*_args, **_kwargs):
        nonlocal attempts
        attempts += 1
        return _Response(b"")

    evidence = OfficialAuthorDocumentFetcher(opener=opener).fetch(
        _claim(), _profile("https://example.com/release/1"), article_date=date(2025, 1, 4)
    )

    assert evidence.status == "UNRESOLVED"
    assert evidence.reason_code == "OFFICIAL_AUTHOR_HOST_NOT_TRUSTED"
    assert attempts == 0


def test_holds_when_official_document_was_published_after_article() -> None:
    raw = "게시일 2025-01-09 2024년 미국 라면 수출 증가율은 70.3%".encode()
    fetcher = OfficialAuthorDocumentFetcher(opener=lambda *_args, **_kwargs: _Response(raw))

    evidence = fetcher.fetch(_claim(), _profile(), article_date=date(2025, 1, 4))

    assert evidence.status == "AS_OF_UNAVAILABLE"
    assert evidence.reason_code == "AS_OF_UNAVAILABLE"
    assert evidence.official_value == 70.3
