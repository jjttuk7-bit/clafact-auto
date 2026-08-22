from datetime import date

from core.kosis_fetcher import KosisValue
from schemas.candidate import KosisCandidateSchema
from schemas.claim import ClaimSchema
from schemas.concept import StandardConceptSchema


def test_official_evidence_service_runs_catalog_and_verdict_through_one_core_entrypoint() -> None:
    from core.official_evidence_service import OfficialEvidenceService

    claim = ClaimSchema(
        claim_id="employment-202412",
        source_sentence="2024년 12월 취업자 수는 2804만1000명이었다.",
        indicator="취업자 수",
        value=28_041_000,
        unit="명",
        time="2024년 12월",
        frequency="MONTHLY",
        region="한국",
        parse_status="AUTO_OK",
    )
    concept = StandardConceptSchema(
        concept_id="C000008",
        canonical_name="취업자 수",
        standard_key="employment_count",
        status="MATCHED",
    )
    candidate = KosisCandidateSchema(
        org_id="101",
        tbl_id="DT_1DA7001S",
        tbl_name="경제활동인구조사",
        core_item_ids=["T30"],
        core_item_names=["취업자 수"],
        unit_names=["천명"],
        item_units={"T30": "천명"},
        dimension_ids=["B"],
        dimension_names=["성별"],
        dimension_members={"B": ["계"]},
        dimension_member_codes={"B": {"계": "0"}},
        frequency="월",
        metadata_status="OFFICIAL_METADATA_READY",
    )
    observed: list[tuple[str, str]] = []

    class Fetcher:
        def fetch(self, cell, *, article_date):
            assert article_date == date(2025, 1, 16)
            assert cell.canonical_key
            return KosisValue(28_041.1, "SUCCESS", "a" * 64, "API")

    service = OfficialEvidenceService(
        concept_mapper=lambda input_claim: concept,
        catalog_resolver=lambda input_claim, input_concept: observed.append((input_claim.claim_id, input_concept.concept_id)) or [candidate],
        official_fetcher=Fetcher(),
    )

    result = service.resolve(claim, article_date=date(2025, 1, 16))

    assert observed == [("employment-202412", "C000008")]
    assert result.concept == concept
    assert result.candidates == [candidate]
    assert result.verdict.route_status == "AUTO"
    assert result.verdict.verdict == "MATCH"

def test_official_evidence_service_preserves_safe_catalog_diagnostics() -> None:
    from core.official_evidence_service import CatalogResolution, OfficialEvidenceService

    claim = ClaimSchema(claim_id="c", source_sentence="", indicator="통계", parse_status="AUTO_OK")
    concept = StandardConceptSchema(concept_id="C", canonical_name="통계", standard_key="stat", status="MATCHED")
    service = OfficialEvidenceService(
        concept_mapper=lambda _: concept,
        catalog_resolver=lambda *_: CatalogResolution(
            candidates=[],
            diagnostics={"attempted_queries": 3, "failed_queries": 1, "empty_queries": 2, "candidate_count": 0},
        ),
        official_fetcher=object(),
    )

    result = service.resolve(claim, article_date=date(2025, 1, 1))

    assert result.catalog_diagnostics == {
        "attempted_queries": 3, "failed_queries": 1, "empty_queries": 2, "candidate_count": 0,
    }

def test_official_evidence_service_routes_total_metadata_failure_to_named_hold() -> None:
    from core.official_evidence_service import CatalogResolution, OfficialEvidenceService

    claim = ClaimSchema(claim_id="c", source_sentence="", indicator="통계", parse_status="AUTO_OK")
    concept = StandardConceptSchema(concept_id="C", canonical_name="통계", standard_key="stat", status="MATCHED")
    diagnostics = {
        "metadata_itm_attempted": 2,
        "metadata_itm_succeeded": 0,
        "metadata_itm_failed": 2,
        "metadata_unavailable": 1,
    }
    service = OfficialEvidenceService(
        concept_mapper=lambda _: concept,
        catalog_resolver=lambda *_: CatalogResolution(candidates=[], diagnostics=diagnostics),
        official_fetcher=object(),
    )

    result = service.resolve(claim, article_date=date(2025, 1, 1))

    assert result.verdict.route_status == "HOLD"
    assert result.verdict.reason_code == "KOSIS_METADATA_UNAVAILABLE"
    assert result.catalog_diagnostics == diagnostics
