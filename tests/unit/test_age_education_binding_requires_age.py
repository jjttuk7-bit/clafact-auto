from core.catalog_binding import apply_catalog_binding
from schemas.candidate import KosisCandidateSchema
from schemas.claim import ClaimSchema
from schemas.concept import StandardConceptSchema


def test_age_education_table_is_not_forced_without_age_scope() -> None:
    claim = ClaimSchema(
        claim_id="EDUCATION-ONLY", source_sentence="2025년 1분기 고졸 실업률은 5.5%였다.",
        indicator="실업률", value=5.5, unit="%", time="2025년 1분기",
        frequency="분기", dimension={"학력": "고졸"},
        calculation="DIRECT_VALUE", parse_status="AUTO_OK",
    )
    concept = StandardConceptSchema(
        concept_id="TEST", canonical_name="실업률", standard_key="unemployment_rate",
        matched_alias="실업률", status="MATCHED",
    )
    candidates = [
        KosisCandidateSchema(
            org_id="101", tbl_id=table, tbl_name="실업률",
            core_item_ids=["T80"], core_item_names=["실업률"],
            unit_names=["%"], item_units={"T80": "%"}, frequency="분기",
            metadata_status="OFFICIAL_METADATA_READY",
        )
        for table in ("DT_1DA7103S", "DT_1DA7105S")
    ]

    assert apply_catalog_binding(claim, concept, candidates) == candidates

