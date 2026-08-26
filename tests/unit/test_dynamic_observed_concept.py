from datetime import date

from core.dynamic_kosis_verifier import verify_claim_against_kosis
from core.kosis_fetcher import KosisValue
from schemas.candidate import KosisCandidateSchema
from schemas.claim import ClaimSchema
from schemas.concept import StandardConceptSchema


def test_dynamic_observed_concept_does_not_trigger_official_member_code_filter() -> None:
    claim = ClaimSchema(
        claim_id="farm-population",
        source_sentence="2024년 농가 인구는 200만 명이었다.",
        indicator="농가 인구",
        value=2_000_000,
        unit="명",
        time="2024년",
        frequency="년",
        calculation="DIRECT_VALUE",
        parse_status="AUTO_OK",
    )
    concept = StandardConceptSchema(
        concept_id="OBSERVED:9a07668438c2863d",
        canonical_name="농가 인구",
        standard_key="observed_indicator_9a07668438c2863d",
        matched_alias="농가 인구",
        kosis_search_terms=["농가 인구"],
        status="MATCHED",
    )
    candidate = KosisCandidateSchema(
        org_id="101",
        tbl_id="INH_1EA1011_01",
        tbl_name="농가인구",
        core_item_ids=["T02"],
        core_item_names=["농가인구"],
        unit_names=["천명"],
        item_units={"T02": "천명"},
        frequency="년",
        source_stat_id="OFFICIAL_STRUCTURAL_COORDINATE_RULE",
        metadata_status="OFFICIAL_METADATA_READY",
    )

    class Fetcher:
        def fetch(self, _cell, *, article_date):
            return KosisValue(2000.0, "SUCCESS", "hash", "API")

    verdict = verify_claim_against_kosis(
        claim,
        concept,
        [candidate],
        article_date=date(2025, 4, 17),
        official_fetcher=Fetcher(),
    )

    assert verdict.route_status == "AUTO"
    assert verdict.verdict == "MATCH"
