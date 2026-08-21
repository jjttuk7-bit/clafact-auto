from datetime import date

from core.dynamic_kosis_verifier import verify_claim_against_kosis
from core.official_author_fallback import OfficialAuthorFallbackValue
from core.kosis_fetcher import KosisValue
from schemas.candidate import KosisCandidateSchema
from schemas.claim import ClaimSchema
from schemas.concept import StandardConceptSchema
from schemas.official_author import OfficialAuthorEvidenceSchema


def _claim() -> ClaimSchema:
    return ClaimSchema(
        claim_id="rice-area", source_sentence="2025년 벼 재배면적은 677,597ha였다.",
        indicator="벼 재배면적", value=677597.0, unit="ha", time="2025년",
        frequency="년", region="한국", calculation="DIRECT_VALUE", parse_status="AUTO_OK",
    )


def _concept() -> StandardConceptSchema:
    return StandardConceptSchema(
        concept_id="crop_area", canonical_name="재배면적", standard_key="crop_area",
        kosis_search_terms=["재배면적"], status="MATCHED",
    )


def _unresolved_candidate() -> KosisCandidateSchema:
    return KosisCandidateSchema(
        org_id="101", tbl_id="DT_UNRESOLVED", tbl_name="농업통계",
        core_item_ids=["T1"], core_item_names=["생산량"], unit_names=["ha"],
        frequency="년", metadata_status="OFFICIAL_METADATA_READY",
    )


class NoKosisValueFetcher:
    def fetch(self, *_args, **_kwargs):
        raise AssertionError("coordinate failure must happen before KOSIS value fetch")


class FixedFallback:
    def __init__(self) -> None:
        self.calls = 0

    def fetch(self, *, claim, concept, article_date):
        self.calls += 1
        assert claim.claim_id == "rice-area"
        assert concept.standard_key == "crop_area"
        assert article_date == date(2025, 9, 1)
        return OfficialAuthorFallbackValue(
            value=677597.0,
            evidence=OfficialAuthorEvidenceSchema(
                source_url="https://kostat.go.kr/release.pdf", published_at=date(2025, 8, 28),
                document_hash="sha256:" + "a" * 64,
                extraction_snippet="2025년 벼 재배면적은 677,597ha",
                extraction_context="national cultivated area",
            ),
        )


def test_kosis_coordinate_failure_then_official_author_direct_value_matches() -> None:
    fallback = FixedFallback()
    verdict = verify_claim_against_kosis(
        _claim(), _concept(), [_unresolved_candidate()], article_date=date(2025, 9, 1),
        official_fetcher=NoKosisValueFetcher(), official_author_fallback=fallback,
    )
    assert fallback.calls == 1
    assert verdict.route_status == "AUTO"
    assert verdict.verdict == "MATCH"
    assert verdict.calculated_value == 677597.0
    assert verdict.official_value_provenance[-1].source == "OFFICIAL_AUTHOR_RELEASE"
    assert verdict.official_value_provenance[-1].official_author_evidence is not None
    assert verdict.execution_trace is not None
    assert any(event.output_ref == "KOSIS_ATTEMPT:NO_EVIDENCE_COORDINATE_CANDIDATE" for event in verdict.execution_trace.events)


def test_kosis_success_bypasses_official_author_fallback() -> None:
    class KosisFetcher:
        def fetch(self, *_args, **_kwargs):
            return KosisValue(677597.0, "SUCCESS", "kosis", "API")

    fallback = FixedFallback()
    candidate = KosisCandidateSchema(
        org_id="101", tbl_id="DT_RICE", tbl_name="벼 재배면적", core_item_ids=["T1"],
        core_item_names=["재배면적"], unit_names=["ha"], frequency="년",
        metadata_status="OFFICIAL_METADATA_READY",
    )
    verdict = verify_claim_against_kosis(
        _claim(), _concept(), [candidate], article_date=date(2025, 9, 1),
        official_fetcher=KosisFetcher(), official_author_fallback=fallback,
    )
    assert verdict.route_status == "AUTO"
    assert fallback.calls == 0


def test_fallback_failure_holds_with_stable_reason_and_kosis_trace() -> None:
    class EmptyFallback:
        def fetch(self, **_kwargs):
            return None

    verdict = verify_claim_against_kosis(
        _claim(), _concept(), [_unresolved_candidate()], article_date=date(2025, 9, 1),
        official_fetcher=NoKosisValueFetcher(), official_author_fallback=EmptyFallback(),
    )
    assert verdict.route_status == "HOLD"
    assert verdict.reason_code == "OFFICIAL_AUTHOR_VALUE_UNRESOLVED"
    assert verdict.execution_trace is not None
    assert any(event.output_ref == "KOSIS_ATTEMPT:NO_EVIDENCE_COORDINATE_CANDIDATE" for event in verdict.execution_trace.events)


def test_unsupported_calculation_never_calls_fallback() -> None:
    claim = _claim().model_copy(update={"calculation": "GROWTH_RATE", "comparison": {"type": "YEAR_OVER_YEAR"}})
    fallback = FixedFallback()
    verdict = verify_claim_against_kosis(
        claim, _concept(), [_unresolved_candidate()], article_date=date(2025, 9, 1),
        official_fetcher=NoKosisValueFetcher(), official_author_fallback=fallback,
    )
    assert verdict.route_status == "HOLD"
    assert verdict.reason_code == "NO_EVIDENCE_COORDINATE_CANDIDATE"
    assert fallback.calls == 0

def test_only_north_korea_kosis_candidate_runs_fallback_after_hard_guard() -> None:
    fallback = FixedFallback()
    north_korea_candidate = KosisCandidateSchema(
        org_id="101", tbl_id="DT_NK", tbl_name="북한 벼 재배면적", core_item_ids=["T1"],
        core_item_names=["재배면적"], unit_names=["ha"], frequency="년",
        metadata_status="OFFICIAL_METADATA_READY",
    )
    verdict = verify_claim_against_kosis(
        _claim(), _concept(), [north_korea_candidate], article_date=date(2025, 9, 1),
        official_fetcher=NoKosisValueFetcher(), official_author_fallback=fallback,
    )
    assert verdict.route_status == "AUTO"
    assert fallback.calls == 1
    assert verdict.execution_trace is not None
    assert any(event.output_ref == "KOSIS_ATTEMPT:NO_HARD_GUARD_CANDIDATE" for event in verdict.execution_trace.events)
