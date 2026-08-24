from datetime import date

from core.official_author_fallback_service import OfficialAuthorFallbackService
from core.official_evidence_service import OfficialEvidenceResolution
from core.operational_error import OperationalStageError
from core.verdict_engine import make_verdict
from schemas.claim import ClaimSchema
from schemas.concept import StandardConceptSchema
from schemas.official_author import OfficialAuthorEvidence, OfficialAuthorProfile


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


def _profile() -> OfficialAuthorProfile:
    return OfficialAuthorProfile(
        profile_id="food",
        author_name="농림축산식품부",
        indicator_terms=["라면", "수출"],
        trusted_hosts=["mafra.go.kr"],
        documents=[],
    )


class _CatalogFailure:
    def resolve(self, *_args, **_kwargs):
        raise OperationalStageError("KOSIS_CATALOG", "diag")


class _Fetcher:
    def __init__(self, evidence: OfficialAuthorEvidence) -> None:
        self.evidence = evidence
        self.calls = 0

    def fetch(self, *_args, **_kwargs) -> OfficialAuthorEvidence:
        self.calls += 1
        return self.evidence


def test_runs_official_author_only_after_kosis_catalog_failure() -> None:
    evidence = OfficialAuthorEvidence(
        status="VERIFIED",
        author_name="농림축산식품부",
        profile_id="food",
        reference_period="2024",
        official_value=70.3,
        unit="%",
        published_at=date(2025, 1, 2),
        source_url="https://www.mafra.go.kr/release/1",
        retrieved_at="2025-01-02T00:00:00Z",
        content_hash="a" * 64,
    )
    fetcher = _Fetcher(evidence)
    concept = StandardConceptSchema(
        concept_id="C1", canonical_name="수출 증가율", standard_key="export_growth", status="MATCHED"
    )
    service = OfficialAuthorFallbackService(
        canonical_service=_CatalogFailure(),
        concept_mapper=lambda _claim: concept,
        profiles=[_profile()],
        document_fetcher=fetcher,
    )

    result = service.resolve(_claim(), article_date=date(2025, 1, 4))

    assert fetcher.calls == 1
    assert result.verdict.verdict == "MATCH"
    assert result.verdict.route_status == "AUTO"
    assert result.verdict.official_value_provenance[0].source == "OFFICIAL_DOCUMENT"
    assert result.official_author_evidence == evidence
    assert [event.stage for event in result.verdict.execution_trace.events][-4:] == [
        "OFFICIAL_AUTHOR_SEARCH", "OFFICIAL_AUTHOR_FETCH", "CALCULATION", "VERDICT"
    ]


def test_does_not_run_fallback_when_canonical_returns_a_result() -> None:
    concept = StandardConceptSchema(
        concept_id="C1", canonical_name="수출 증가율", standard_key="export_growth", status="MATCHED"
    )
    canonical_result = OfficialEvidenceResolution(
        concept=concept,
        candidates=[],
        verdict=make_verdict("c1", 70.3, [70.3], 70.3),
    )

    class Canonical:
        def resolve(self, *_args, **_kwargs):
            return canonical_result

    fetcher = _Fetcher(OfficialAuthorEvidence(
        status="UNRESOLVED", author_name="농림축산식품부", profile_id="food"
    ))
    service = OfficialAuthorFallbackService(
        canonical_service=Canonical(), concept_mapper=lambda _claim: concept,
        profiles=[_profile()], document_fetcher=fetcher,
    )

    result = service.resolve(_claim(), article_date=date(2025, 1, 4))

    assert result is canonical_result
    assert fetcher.calls == 0


def test_preserves_as_of_hold_with_official_document_audit() -> None:
    evidence = OfficialAuthorEvidence(
        status="AS_OF_UNAVAILABLE",
        author_name="국토교통부",
        profile_id="construction",
        reference_period="2024",
        official_value=1_000_900_000_000.0,
        unit="USD",
        published_at=date(2025, 1, 9),
        source_url="https://www.molit.go.kr/release/1",
        retrieved_at="2025-01-09T00:00:00Z",
        content_hash="b" * 64,
        reason_code="AS_OF_UNAVAILABLE",
    )
    profile = OfficialAuthorProfile(
        profile_id="construction", author_name="국토교통부",
        indicator_terms=["해외", "건설"], trusted_hosts=["molit.go.kr"], documents=[],
    )
    service = OfficialAuthorFallbackService(
        canonical_service=_CatalogFailure(),
        concept_mapper=lambda _claim: StandardConceptSchema(
            concept_id="C2", canonical_name="해외건설", standard_key="construction", status="MATCHED"
        ),
        profiles=[profile], document_fetcher=_Fetcher(evidence),
    )

    result = service.resolve(ClaimSchema(
        claim_id="c2", source_sentence="해외 건설 누적 수주액 1조달러",
        indicator="해외 건설 누적 수주액", value=1_000_000_000_000,
        unit="USD", time="2024", calculation="THRESHOLD", parse_status="AUTO_OK",
    ), article_date=date(2025, 1, 4))

    assert result.verdict.route_status == "HOLD"
    assert result.verdict.reason_code == "AS_OF_UNAVAILABLE"
    assert result.verdict.official_value_provenance[0].content_hash == "b" * 64
    assert result.verdict.official_value_provenance[0].publication.status == "UNRESOLVED"
