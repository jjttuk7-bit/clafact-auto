from __future__ import annotations

from datetime import date

from core.official_publication_claim_verifier import OfficialPublicationClaimVerifier
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
