from __future__ import annotations

from datetime import date

from core.official_publication_claim_verifier import OfficialPublicationClaimVerifier
from core.verdict_engine import make_verdict
from schemas.claim import ClaimSchema
from schemas.pipeline_trace import PipelineTraceSchema
from schemas.verdict import (
    OfficialPublicationProvenanceSchema,
    OfficialValueProvenanceSchema,
)


class _Response:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self) -> bytes:
        return self._body


def _claim() -> ClaimSchema:
    return ClaimSchema(
        claim_id="birth-202501",
        source_sentence="2025년 1월 출생아 수는 전년 동월 대비 11.6% 증가했다.",
        indicator="출생아 수",
        value=11.6,
        unit="%",
        time="2025년 1월",
        frequency="MONTHLY",
        comparison={"type": "YEAR_OVER_YEAR", "reference_period": "2024년 1월"},
        calculation="GROWTH_RATE",
        condition={"direction": "INCREASE"},
        parse_status="AUTO_OK",
    )


def _as_of_verdict(*, host: str = "www.kostat.go.kr", published_at: date = date(2025, 3, 26)):
    publication = OfficialPublicationProvenanceSchema(
        status="VERIFIED",
        published_at=published_at,
        source_url=f"https://{host}/board/release-1",
        retrieved_at="2026-08-24T00:00:00Z",
        reference_period="2025-01",
        content_hash="a" * 64,
    )
    provenance = OfficialValueProvenanceSchema(
        evidence_key="KOSIS:2025-01",
        source="API",
        source_url="https://kosis.kr/openapi/value",
        retrieved_at="2026-08-24T00:00:00Z",
        content_hash="b" * 64,
        publication=publication,
    )
    trace = (
        PipelineTraceSchema(
            claim_id="birth-202501", preprocess_version="1.0", claim_schema_version="1.0"
        )
        .pass_stage("CLAIM_PARSE")
        .pass_stage("SEMANTIC_MAPPING")
        .pass_stage("CATALOG_SEARCH")
        .pass_stage("HARD_GUARD")
        .pass_stage("SEMANTIC_MATCH")
        .pass_stage("EVIDENCE_CELL")
        .hold("OFFICIAL_VALUE_FETCH", "AS_OF_UNAVAILABLE")
    )
    return make_verdict("birth-202501", 11.6, [], None, trace=trace).model_copy(
        update={
            "reason_code": "AS_OF_UNAVAILABLE",
            "official_value_provenance": [provenance],
        }
    )


def _html(rate: str = "11.6", direction: str = "증가") -> bytes:
    return (
        "<html><title>2025년 1월 인구동향</title><body>"
        "게시일 2025-03-26 "
        f"출생아 수는 23,947명으로 전년동월대비 {rate}% {direction} "
        "</body></html>"
    ).encode()


def test_recovers_as_of_hold_from_exact_pre_article_kostat_release() -> None:
    calls: list[str] = []

    def opener(request, *, timeout):
        calls.append(request.full_url)
        assert timeout == 15
        return _Response(_html())

    result = OfficialPublicationClaimVerifier(opener=opener).recover(
        _claim(), _as_of_verdict(), article_date=date(2025, 6, 25)
    )

    assert calls == ["https://www.kostat.go.kr/board/release-1"]
    assert result.route_status == "AUTO"
    assert result.verdict == "MATCH"
    assert result.calculated_value == 11.6
    assert result.evidence_values == [11.6]
    assert result.official_value_provenance[-1].source == "OFFICIAL_DOCUMENT"
    assert result.official_value_provenance[-1].publication.reference_period == "2025-01"
    assert [event.stage for event in result.execution_trace.events][-4:] == [
        "OFFICIAL_AUTHOR_SEARCH",
        "OFFICIAL_AUTHOR_FETCH",
        "CALCULATION",
        "VERDICT",
    ]


def test_officially_different_value_becomes_auditable_mismatch() -> None:
    result = OfficialPublicationClaimVerifier(
        opener=lambda *_args, **_kwargs: _Response(_html(rate="9.9"))
    ).recover(_claim(), _as_of_verdict(), article_date=date(2025, 6, 25))

    assert result.route_status == "AUTO"
    assert result.verdict == "MISMATCH"
    assert result.calculated_value == 9.9


def test_does_not_recover_wrong_direction_or_period() -> None:
    cases = [
        (_html(direction="감소"), _claim(), _as_of_verdict()),
        (_html(), _claim().model_copy(update={"time": "2025년 2월"}), _as_of_verdict()),
    ]
    for body, claim, verdict in cases:
        original = verdict
        result = OfficialPublicationClaimVerifier(
            opener=lambda *_args, **_kwargs: _Response(body)
        ).recover(claim, verdict, article_date=date(2025, 6, 25))
        assert result is original
        assert result.reason_code == "AS_OF_UNAVAILABLE"


def test_does_not_fetch_untrusted_or_post_article_publication() -> None:
    calls = 0

    def opener(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        return _Response(_html())

    verifier = OfficialPublicationClaimVerifier(opener=opener)
    assert verifier.recover(
        _claim(), _as_of_verdict(host="example.com"), article_date=date(2025, 6, 25)
    ).reason_code == "AS_OF_UNAVAILABLE"
    assert verifier.recover(
        _claim(), _as_of_verdict(published_at=date(2025, 7, 1)), article_date=date(2025, 6, 25)
    ).reason_code == "AS_OF_UNAVAILABLE"
    assert calls == 0


def test_only_runs_for_as_of_growth_rate_claims() -> None:
    calls = 0

    def opener(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        return _Response(_html())

    verifier = OfficialPublicationClaimVerifier(opener=opener)
    ordinary = _as_of_verdict().model_copy(update={"reason_code": "FETCH_FAILED"})
    direct = _claim().model_copy(update={"calculation": "DIRECT_VALUE"})

    assert verifier.recover(_claim(), ordinary, article_date=date(2025, 6, 25)) is ordinary
    as_of = _as_of_verdict()
    assert verifier.recover(direct, as_of, article_date=date(2025, 6, 25)) is as_of
    assert calls == 0
