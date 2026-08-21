from datetime import date
import ssl

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


def test_default_kosis_publication_opener_uses_tls_12_context(monkeypatch) -> None:
    observed: dict[str, object] = {}

    def fake_urlopen(_request, *, timeout, context):
        observed["context"] = context
        return Response(b"[]")

    monkeypatch.setattr(publication, "urlopen", fake_urlopen)

    with publication._default_kosis_opener("https://kosis.kr/test", timeout=5):
        pass

    context = observed["context"]
    assert isinstance(context, ssl.SSLContext)
    assert context.maximum_version == ssl.TLSVersion.TLSv1_2

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

def test_publication_lookup_finds_exact_kostat_release_when_kosis_has_only_schedule() -> None:
    explanation = (
        '[{"statsNm":"경제활동인구조사","pubDate":"조사대상월 익월 15일경",'
        '"publictMth":"KOSIS 및 보도자료"}]'
    ).encode("utf-8")
    search_page = (
        '<a href="/board.es?act=view&bid=210&list_no=434801">'
        '2024년 12월 및 연간 고용동향</a>'
    ).encode("utf-8")
    release_page = (
        '<h1>2024년 12월 및 연간 고용동향</h1>'
        '<p>연관조사 경제활동인구조사</p><p>게시일 2025-01-15</p>'
    ).encode("utf-8")

    def opener(request, *, timeout):
        if "statisticsExplData" in request.full_url:
            return Response(explanation)
        if "act=list" in request.full_url:
            return Response(search_page)
        return Response(release_page)

    result = KosisPublicationLookup("secret", opener=opener, retries=1).fetch(
        "101", "DT_1DA7001S", period="2024-12"
    )

    assert result.status == "VERIFIED"
    assert result.published_at == date(2025, 1, 15)
    assert result.source_url == "https://www.kostat.go.kr/board.es?act=view&bid=210&list_no=434801"


def test_publication_lookup_uses_official_item_name_when_table_name_is_generic() -> None:
    explanation = ('[{"statsNm":"남한 경지면적","pubDate":"조사기준 년 익년 2월","publictMth":"KOSIS 및 보도자료"}]').encode("utf-8")
    search_page = ('<a href="/board.es?act=view&bid=213&list_no=445001">2025년 벼 재배면적조사 결과</a>').encode("utf-8")
    release_page = ('<h1>2025년 벼 재배면적조사 결과</h1><p>게시일 2025-10-02</p>').encode("utf-8")

    def opener(request, *, timeout):
        if "statisticsExplData" in request.full_url:
            return Response(explanation)
        if "bid=229" in request.full_url and "keyWord=2025%EB%85%84+%EB%B2%BC+%EC%9E%AC%EB%B0%B0%EB%A9%B4%EC%A0%81" in request.full_url:
            return Response(search_page)
        if "act=list" in request.full_url:
            return Response(b"")
        return Response(release_page)

    result = KosisPublicationLookup("secret", opener=opener, retries=1).fetch(
        "101", "DT_RICE", period="2025", search_terms=["벼 재배면적"]
    )

    assert result.status == "VERIFIED"
    assert result.published_at == date(2025, 10, 2)

    assert result.published_at == date(2025, 10, 2)
def test_release_links_parse_kostat_javascript_detail_links() -> None:
    raw = (
        '<a class="board_link" '
        'href="javascript:addSearchParam(\'/board.es?mid=a10301010000&bid=213&act=view&list_no=439120\');">'
        '<span></span><span>2025년 10월 소비자물가동향</span></a>'
    ).encode("utf-8")

    assert publication._release_links(raw) == [
        (
            "https://www.kostat.go.kr/board.es?mid=a10301010000&bid=213&act=view&list_no=439120",
            "2025년 10월 소비자물가동향",
        )
    ]

def test_publication_lookup_accepts_matching_release_title_when_body_uses_different_stat_label() -> None:
    explanation = (
        '[{"statsNm":"소비자물가조사","pubDate":"조사대상월 익월",'
        '"publictMth":"KOSIS 및 보도자료"}]'
    ).encode("utf-8")
    search_page = (
        '<a href="javascript:addSearchParam(\'/board.es?mid=a10301010000&bid=213&act=view&list_no=439120\');">'
        '<span>2025년 10월 소비자물가동향</span></a>'
    ).encode("utf-8")
    release_page = (
        '<h1>2025년 10월 소비자물가동향</h1><p>게시일 2025-11-04</p>'
    ).encode("utf-8")

    def opener(request, *, timeout):
        if "statisticsExplData" in request.full_url:
            return Response(explanation)
        if "act=list" in request.full_url:
            return Response(search_page)
        return Response(release_page)

    result = KosisPublicationLookup("secret", opener=opener, retries=1).fetch(
        "101", "DT_CPI", period="202510"
    )

    assert result.status == "VERIFIED"
    assert result.published_at == date(2025, 11, 4)

def test_kostat_press_search_uses_official_title_search_parameters() -> None:
    explanation = (
        '[{"statsNm":"소비자물가조사","pubDate":"조사대상월 익월",'
        '"publictMth":"KOSIS 및 보도자료"}]'
    ).encode("utf-8")
    seen: list[str] = []

    def opener(request, *, timeout):
        seen.append(request.full_url)
        return Response(explanation)

    KosisPublicationLookup("secret", opener=opener, retries=1).fetch(
        "101", "DT_CPI", period="202510"
    )

    search_url = next(url for url in seen if "act=list" in url)
    assert "bid=213" in search_url
    assert "keyField=T" in search_url
    assert "keyWord=2025%EB%85%84+10%EC%9B%94+%EC%86%8C%EB%B9%84%EC%9E%90%EB%AC%BC%EA%B0%80%EB%8F%99%ED%96%A5" in search_url

def test_kostat_search_uses_human_period_label() -> None:
    assert publication._period_label("2024-12") == "2024년 12월"
    assert publication._period_label("2024Q1") == "2024년 1분기"

def test_official_release_transport_failure_is_not_downgraded_to_unresolved() -> None:
    explanation = (
        '[{"pubDate":"매월 15일경",'
        '"publictMth":"https://kostat.go.kr/board.es?act=view&list_no=4"}]'
    ).encode("utf-8")

    def opener(request, *, timeout):
        if "statisticsExplData" in request.full_url:
            return Response(explanation)
        raise OSError("network unavailable")

    result = KosisPublicationLookup("secret", opener=opener, retries=1).fetch(
        "101", "DT_EMPLOYMENT", period="2024-12"
    )

    assert result.status == "FETCH_FAILED"
    assert result.source_url == "https://kostat.go.kr/board.es?act=view&list_no=4"
def test_extract_official_url_decodes_html_query_and_removes_attached_statistics_name() -> None:
    value = (
        'https://mods.go.kr/board.es?mid=a10301010000&amp;bid=210&amp;'
        'list_no=445948&amp;act=view&amp;mainXml=Y경제활동인구'
    )

    assert publication._extract_official_url(value) == (
        'https://mods.go.kr/board.es?mid=a10301010000&bid=210&'
        'list_no=445948&act=view&mainXml=Y'
    )

def test_official_release_request_uses_browser_compatible_user_agent() -> None:
    explanation = (
        '[{"pubDate":"매월 15일경",'
        '"publictMth":"https://kostat.go.kr/board.es?act=view&list_no=434801"}]'
    ).encode("utf-8")
    release = (
        "<h1>2024년 12월 고용동향</h1><span>게시일 2025-01-15</span>"
    ).encode("utf-8")
    requests = []

    def opener(request, *, timeout):
        requests.append(request)
        return Response(release if "kostat.go.kr" in request.full_url else explanation)

    KosisPublicationLookup("secret", opener=opener, retries=1).fetch(
        "101", "DT_EMPLOYMENT", period="2024-12"
    )

    assert requests[1].get_header("User-agent").startswith("Mozilla/")
def test_official_release_transport_failure_is_retried_before_hold() -> None:
    explanation = (
        '[{"pubDate":"매월 15일경",'
        '"publictMth":"https://kostat.go.kr/board.es?act=view&list_no=7"}]'
    ).encode("utf-8")
    release = "<h1>2024년 12월 고용동향</h1><span>게시일 2025-01-15</span>".encode("utf-8")
    release_attempts = 0

    def opener(request, *, timeout):
        nonlocal release_attempts
        if "statisticsExplData" in request.full_url:
            return Response(explanation)
        release_attempts += 1
        if release_attempts == 1:
            raise OSError("temporary reset")
        return Response(release)

    result = KosisPublicationLookup("secret", opener=opener, retries=2).fetch(
        "101", "DT_EMPLOYMENT", period="2024-12"

    )

    assert result.status == "VERIFIED"
    assert result.published_at == date(2025, 1, 15)
    assert release_attempts == 2


def test_employment_release_search_uses_official_board_and_december_annual_title() -> None:
    assert publication._press_release_board_id("경제활동인구조사") == "210"
    assert publication._press_release_queries("경제활동인구조사", "2024-12") == [
        "2024년 12월 및 연간 고용동향"
    ]

def test_annual_employment_release_search_uses_december_annual_title() -> None:
    assert publication._press_release_queries("경제활동인구조사", "2024") == [
        "2024년 12월 및 연간 고용동향"

    ]
def test_extract_official_release_value_requires_period_indicator_and_unit() -> None:
    text = "2025년 벼 재배면적은 677,597ha로 전년 697,713ha보다 2.9% 감소"

    assert publication.extract_official_release_value(
        text, period="2025", indicator="벼 재배면적", unit="ha"
    ) == 677_597.0
    assert publication.extract_official_release_value(
        text, period="2025", indicator="고추 재배면적", unit="ha"
    ) is None



def test_release_links_decode_cp949_statistics_korea_list_titles() -> None:
    raw = (
        '<a href="board.es?act=view&amp;list_no=438232">'
        '2025년 논벼(쌀) 재배면적조사 결과</a>'
    ).encode("cp949")

    links = publication._release_links(raw)

    assert links == [(
        "https://www.kostat.go.kr/board.es?act=view&list_no=438232",
        "2025년 논벼(쌀) 재배면적조사 결과",
    )]


def test_html_text_honors_declared_cp949_charset() -> None:
    raw = '<meta charset="euc-kr"><span>게시일 2025-08-28</span>'.encode("cp949")

    assert publication._html_text(raw).strip() == "게시일 2025-08-28"