from datetime import date

import core.kosis_publication as publication
from core.kosis_publication import KosisPublicationLookup


class Response:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self) -> bytes:
        return self._payload


def test_publication_lookup_fetches_official_explanation_and_preserves_provenance() -> None:
    observed: dict[str, object] = {}

    def opener(request, *, timeout):
        observed["url"] = request.full_url
        observed["timeout"] = timeout
        return Response(
            b'[{"statsNm":"Employment Survey"},'
            b'{"pubPeriod":"Monthly"},'
            b'{"pubDate":"2025-01-15"},'
            b'{"publictMth":"https://kostat.go.kr/board.es?list_no=434801"}]'
        )

    lookup = KosisPublicationLookup("secret-key", opener=opener, retries=1)
    result = lookup.fetch("101", "DT_EMPLOYMENT")

    assert result.status == "VERIFIED"
    assert result.published_at == date(2025, 1, 15)
    assert result.pub_period == "Monthly"
    assert result.publication_method_url == "https://kostat.go.kr/board.es?list_no=434801"
    assert result.source_url == (
        "https://kosis.kr/openapi/statisticsExplData.do?method=getList&format=json"
        "&jsonVD=Y&orgId=101&tblId=DT_EMPLOYMENT&metaItm=All"
    )
    assert len(result.content_hash) == 64
    assert result.retrieved_at.endswith("Z")
    assert "secret-key" not in result.source_url
    assert "apiKey=secret-key" in str(observed["url"])
    assert observed["timeout"] == 10


def test_publication_lookup_does_not_invent_date_from_schedule_text() -> None:
    lookup = KosisPublicationLookup(
        "secret-key",
        opener=lambda *_args, **_kwargs: Response(
            '[{"pubPeriod":"월","pubDate":"매월 15일경",'
            '"publictMth":"KOSIS 및 보도자료"}]'.encode("utf-8")
        ),
        retries=1,
    )

    result = lookup.fetch("101", "DT")

    assert result.status == "UNRESOLVED"
    assert result.published_at is None
    assert result.pub_date_text == "매월 15일경"


def test_publication_lookup_rejects_kosis_error_payload() -> None:
    lookup = KosisPublicationLookup(
        "secret-key",
        opener=lambda *_args, **_kwargs: Response(b'{"err":"30","errMsg":"invalid"}'),
        retries=1,
    )

    result = lookup.fetch("101", "DT")

    assert result.status == "FETCH_FAILED"
    assert result.published_at is None

def test_publication_lookup_follows_official_release_url_for_exact_period_date() -> None:
    explanation = (
        '[{"pubPeriod":"월","pubDate":"조사대상월 익월 15일경",'
        '"publictMth":"https://kostat.go.kr/board.es?act=view&list_no=434801"}]'
    ).encode("utf-8")
    release = """
        <html><head><title>2024년 12월 및 연간 고용동향</title></head>
        <body><h1>2024년 12월 및 연간 고용동향</h1><span>게시일 2025-01-15</span></body></html>
    """.encode("utf-8")
    requested: list[str] = []

    def opener(request, *, timeout):
        requested.append(request.full_url)
        return Response(release if "kostat.go.kr" in request.full_url else explanation)

    result = KosisPublicationLookup("secret", opener=opener, retries=1).fetch(
        "101", "DT_EMPLOYMENT", period="2024-12"
    )

    assert len(requested) == 2
    assert result.status == "VERIFIED"
    assert result.published_at == date(2025, 1, 15)
    assert result.source_url == "https://kostat.go.kr/board.es?act=view&list_no=434801"
    assert result.pub_date_text == "조사대상월 익월 15일경"
    assert len(result.content_hash) == 64


def test_publication_lookup_rejects_release_page_for_different_period() -> None:
    explanation = (
        '[{"pubDate":"매월 15일경",'
        '"publictMth":"https://kostat.go.kr/board.es?act=view&list_no=2"}]'
    ).encode("utf-8")
    release = "<h1>2025년 1월 고용동향</h1><span>게시일 2025-02-15</span>".encode("utf-8")

    def opener(request, *, timeout):
        return Response(release if "kostat.go.kr" in request.full_url else explanation)

    result = KosisPublicationLookup("secret", opener=opener, retries=1).fetch(
        "101", "DT_EMPLOYMENT", period="2024-12"
    )

    assert result.status == "UNRESOLVED"
    assert result.published_at is None

def test_conflicting_exact_publication_dates_are_unresolved() -> None:
    payload = (
        '[{"pubDate":"2025-01-15"},{"pubDate":"2025-02-15"},'
        '{"publictMth":"https://kostat.go.kr/board.es?list_no=1"}]'
    ).encode("utf-8")
    lookup = KosisPublicationLookup(
        "secret", opener=lambda *_args, **_kwargs: Response(payload), retries=1
    )

    result = lookup.fetch("101", "DT", period="2024-12")

    assert result.status == "UNRESOLVED"
    assert result.published_at is None

def test_official_release_with_multiple_labeled_dates_is_unresolved() -> None:
    explanation = (
        '[{"pubDate":"매월 15일경",'
        '"publictMth":"https://kostat.go.kr/board.es?act=view&list_no=3"}]'
    ).encode("utf-8")
    release = (
        "<h1>2024년 12월 고용동향</h1>"
        "<div>관련자료 게시일 2025-02-15</div>"
        "<div>본문 게시일 2025-01-15</div>"
    ).encode("utf-8")

    def opener(request, *, timeout):
        return Response(release if "kostat.go.kr" in request.full_url else explanation)

    result = KosisPublicationLookup("secret", opener=opener, retries=1).fetch(
        "101", "DT_EMPLOYMENT", period="2024-12"
    )

    assert result.status == "UNRESOLVED"
    assert result.published_at is None