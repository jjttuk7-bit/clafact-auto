from __future__ import annotations

from datetime import date

from core.official_publication_claim_verifier import OfficialPublicationClaimVerifier, _resolve_pdf_direct_value
from core.official_release_table import OfficialReleaseTable
from core.verdict_engine import make_verdict
from schemas.claim import ClaimSchema
from schemas.pipeline_trace import PipelineTraceSchema
from schemas.verdict import OfficialPublicationProvenanceSchema, OfficialValueProvenanceSchema


class _Response:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self) -> bytes:
        return self._body


def _claim(*, value: float = 2_390_000.0) -> ClaimSchema:
    return ClaimSchema(
        claim_id="resting-202505",
        source_sentence="2025년 5월 쉬었음 인구는 239만명이다.",
        indicator="쉬었음 인구",
        value=value,
        unit="명",
        time="2025년 5월",
        frequency="MONTHLY",
        calculation="DIRECT_VALUE",
        parse_status="AUTO_OK",
    )


def _as_of_verdict():
    publication = OfficialPublicationProvenanceSchema(
        status="VERIFIED",
        published_at=date(2025, 6, 11),
        source_url="https://www.kostat.go.kr/board/release-1",
        retrieved_at="2026-08-27T00:00:00Z",
        reference_period="2025-05",
        content_hash="a" * 64,
    )
    provenance = OfficialValueProvenanceSchema(
        evidence_key="KOSIS:2025-05",
        source="API",
        source_url="https://kosis.kr/openapi/value",
        retrieved_at="2026-08-27T00:00:00Z",
        content_hash="b" * 64,
        publication=publication,
    )
    trace = (
        PipelineTraceSchema(
            claim_id="resting-202505", preprocess_version="1.0", claim_schema_version="1.0"
        )
        .pass_stage("CLAIM_PARSE")
        .pass_stage("SEMANTIC_MAPPING")
        .pass_stage("CATALOG_SEARCH")
        .pass_stage("HARD_GUARD")
        .pass_stage("SEMANTIC_MATCH")
        .pass_stage("EVIDENCE_CELL")
        .hold("OFFICIAL_VALUE_FETCH", "AS_OF_UNAVAILABLE")
    )
    return make_verdict("resting-202505", 2_390_000.0, [], None, trace=trace).model_copy(
        update={"reason_code": "AS_OF_UNAVAILABLE", "official_value_provenance": [provenance]}
    )


def test_direct_value_recovers_from_exact_period_official_attachment(monkeypatch) -> None:
    page = (
        '<html><title>2025년 5월 고용동향</title>'
        '<a class="bvf_name" href="/boardDownload.es?bid=210&list_no=1&seq=1">report.hwpx</a>'
        '</html>'
    ).encode()
    table = OfficialReleaseTable((
        ("< 쉬었음 인구 >",), ("단위: 천명",),
        ("", "2024.", "5", "", "2025.", "4", "", "2025.", "5"),
        ("<전체>", "2,334", "", "", "2,434", "", "", "2,390", ""),
    ))
    calls: list[str] = []

    def opener(request, *, timeout):
        calls.append(request.full_url)
        return _Response(page if "release-1" in request.full_url else b"hwpx")

    monkeypatch.setattr(
        "core.official_publication_claim_verifier.extract_hwpx_tables",
        lambda _raw: [table],
    )
    result = OfficialPublicationClaimVerifier(opener=opener).recover(
        _claim(), _as_of_verdict(), article_date=date(2025, 6, 11)
    )

    assert result.route_status == "AUTO"
    assert result.verdict == "MATCH"
    assert result.calculated_value == 2_390_000.0
    assert result.official_value_provenance[-1].source == "OFFICIAL_DOCUMENT"
    assert result.official_value_provenance[-1].source_url.endswith("seq=1")
    assert len(calls) == 2


def test_direct_value_does_not_use_same_number_outside_indicator_context(monkeypatch) -> None:
    page = '<title>2025년 5월 고용동향</title><a href="/boardDownload.es?bid=210&list_no=1&seq=1">report.hwpx</a>'.encode()
    unrelated = OfficialReleaseTable((
        ("< 취업자 >",), ("단위: 천명",),
        ("", "2025.", "5"), ("<전체>", "2,390"),
    ))
    monkeypatch.setattr(
        "core.official_publication_claim_verifier.extract_hwpx_tables",
        lambda _raw: [unrelated],
    )
    result = OfficialPublicationClaimVerifier(
        opener=lambda request, **_kwargs: _Response(page if "release-1" in request.full_url else b"hwpx")
    ).recover(_claim(), _as_of_verdict(), article_date=date(2025, 6, 11))

    assert result.route_status == "HOLD"
    assert result.reason_code == "AS_OF_UNAVAILABLE"


def test_direct_value_can_produce_auditable_mismatch_from_one_official_row(monkeypatch) -> None:
    page = '<title>2025년 5월 고용동향</title><a href="/boardDownload.es?bid=210&list_no=1&seq=1">report.hwpx</a>'.encode()
    table = OfficialReleaseTable((
        ("< 쉬었음 인구 >",), ("단위: 천명",),
        ("", "2025.", "5"), ("<전체>", "2,390"),
    ))
    monkeypatch.setattr(
        "core.official_publication_claim_verifier.extract_hwpx_tables",
        lambda _raw: [table],
    )
    result = OfficialPublicationClaimVerifier(
        opener=lambda request, **_kwargs: _Response(page if "release-1" in request.full_url else b"hwpx")
    ).recover(_claim(value=2_400_000.0), _as_of_verdict(), article_date=date(2025, 6, 11))

    assert result.route_status == "AUTO"
    assert result.verdict == "MISMATCH"
    assert result.calculated_value == 2_390_000.0


def test_pdf_direct_value_requires_period_indicator_and_unit_context() -> None:
    claim = ClaimSchema(
        claim_id="cpi-pdf", source_sentence="2025년 6월 소비자물가지수는 116.31이었다.",
        indicator="소비자물가지수", value=116.31, unit="지수(2020년=100)",
        time="2025년 6월", frequency="월", calculation="DIRECT_VALUE", parse_status="AUTO_OK",
    )
    text = "2025년 6월 소비자물가동향 소비자물가지수는 116.31(2020=100)로 전월대비 변동없음"
    assert _resolve_pdf_direct_value(claim, text, reference_period="2025-06") == 116.31
    assert _resolve_pdf_direct_value(claim, "2025년 6월 생산자물가지수는 116.31(2020=100)다", reference_period="2025-06") is None
    assert _resolve_pdf_direct_value(claim, text, reference_period="2025-05") is None

def test_pdf_direct_value_parses_compound_korean_scale() -> None:
    claim = ClaimSchema(
        claim_id="employment-pdf", source_sentence="2025년 9월 취업자는 2915만4천명이었다.",
        indicator="취업자", value=29_154_000, unit="명", time="2025년 9월",
        frequency="월", calculation="DIRECT_VALUE", parse_status="AUTO_OK",
    )
    text = "2025년 9월 고용동향 취업자는 2915만4천명으로 전년동월대비 증가"
    assert _resolve_pdf_direct_value(claim, text, reference_period="2025-09") == 29_154_000

def test_pdf_direct_value_ignores_other_table_numbers_before_a_later_unit() -> None:
    claim = ClaimSchema(
        claim_id="employment-table-pdf",
        source_sentence="2025년 9월 취업자는 2915만4천명이었다.",
        indicator="취업자",
        value=29_154_000,
        unit="명",
        time="2025년 9월",
        frequency="월",
        calculation="DIRECT_VALUE",
        parse_status="AUTO_OK",
    )
    text = (
        "2025년 9월 고용동향 "
        "취업자 28,917 1.1 29,154 천명 "
        "취업자 2,915만4천명으로 전년동월대비 증가"
    )

    assert _resolve_pdf_direct_value(claim, text, reference_period="2025-09") == 29_154_000


def test_pdf_direct_value_selects_first_period_assertion_for_total_indicator() -> None:
    claim = ClaimSchema(
        claim_id="birth-total-pdf",
        source_sentence="2025년 3월 출생아 수는 2만1041명이었다.",
        indicator="출생아 수",
        value=21_041,
        unit="명",
        time="2025년 3월",
        frequency="월",
        calculation="DIRECT_VALUE",
        parse_status="AUTO_OK",
    )
    text = "2025년 3월 인구동향 출생아 수는 2만1041명이다. 전년 출생아 수는 1만9700명이었다."

    assert _resolve_pdf_direct_value(claim, text, reference_period="2025-03") == 21_041


def test_pdf_direct_value_requires_claim_age_near_indicator() -> None:
    claim = ClaimSchema(
        claim_id="employment-age-pdf",
        source_sentence="2025년 5월 60세 이상 취업자는 704만9천명이었다.",
        indicator="취업자",
        value=7_049_000,
        unit="명",
        time="2025년 5월",
        frequency="월",
        population="60세 이상",
        dimension={"age": "60세 이상"},
        calculation="DIRECT_VALUE",
        parse_status="AUTO_OK",
    )
    text = (
        "2025년 5월 고용동향 15세 이상 취업자는 2,900만명이다. "
        "60세 이상 취업자는 704만9천명이다."
    )
