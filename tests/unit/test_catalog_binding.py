from core.catalog_binding import apply_catalog_binding
from schemas.candidate import KosisCandidateSchema
from schemas.claim import ClaimSchema
from schemas.concept import StandardConceptSchema


def test_catalog_binding_selects_only_registered_monthly_employment_table() -> None:
    claim = ClaimSchema(
        claim_id="C1",
        source_sentence="2025년 3월 취업자 수는 2858만9000명이었다.",
        indicator="취업자 수",
        value=28589000,
        unit="명",
        time="2025년 3월",
        frequency="월",
        calculation="DIRECT_VALUE",
        parse_status="AUTO_OK",
    )
    concept = StandardConceptSchema(
        concept_id="C000005",
        canonical_name="취업자",
        standard_key="employment_count",
        matched_alias="취업자 수",
        status="MATCHED",
    )
    candidates = [
        KosisCandidateSchema(org_id="101", tbl_id=table_id, tbl_name=table_id, core_item_ids=["T30"], core_item_names=["취업자"], unit_names=["천명"], frequency="월 | 분기 | 년", metadata_status="READY")
        for table_id in ("DT_1DA7001S", "DT_1DA7028S")
    ]

    result = apply_catalog_binding(claim, concept, candidates)

    assert [candidate.tbl_id for candidate in result] == ["DT_1DA7028S"]
