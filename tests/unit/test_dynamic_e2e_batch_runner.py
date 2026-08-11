from datetime import date

from core.dynamic_e2e_batch_runner import run_dynamic_e2e_batch
from schemas.candidate import KosisCandidateSchema
from schemas.claim import ClaimSchema
from schemas.claim_registry import ClaimRegistryRecord
from schemas.concept import StandardConceptSchema


def test_dynamic_batch_verifies_structured_employment_claim_without_profile() -> None:
    record = ClaimRegistryRecord(
        article_id="A1", sentence_id="S1", article_published_at=date(2025, 1, 15), source_ref="test",
        claim=ClaimSchema(
            claim_id="C1", source_sentence="2024년 12월 취업자 수는 2,804만1천 명이었다.",
            indicator="취업자 수", value=28_041_000, unit="명", time="2024년 12월",
            frequency="월", region="한국", parse_status="AUTO_OK",
        ),
    )
    concept = StandardConceptSchema(
        concept_id="employment_count", canonical_name="취업자 수", standard_key="employment_count",
        matched_alias="취업자 수", status="MATCHED",
    )
    catalog = [KosisCandidateSchema(
        org_id="101", tbl_id="DT_1DA7028S", tbl_name="성/종사상지위별 취업자",
        core_item_ids=["T30"], core_item_names=["취업자"], dimension_ids=["B", "J"],
        dimension_names=["성별", "종사상지위"], dimension_members={"B": ["계"], "J": ["계"]},
        dimension_member_codes={"B": {"계": "0"}, "J": {"계": "00"}},
        unit_names=["천명"], frequency="월", metadata_status="OFFICIAL_METADATA_READY",
    )]

    results = run_dynamic_e2e_batch(
        [record], {("A1", "S1"): concept}, catalog,
        api_lookup=lambda _cell: [{"TBL_ID": "DT_1DA7028S", "ITM_ID": "T30", "PRD_DE": "202412", "B": "0", "J": "00", "DT": "28041", "LST_CHN_DE": "2025-01-10"}],
    )

    assert results[0]["route_status"] == "AUTO"
    assert results[0]["verdict"] == "MATCH"
    assert results[0]["profile_id"] is None
    assert results[0]["calculated_value"] == 28_041_000