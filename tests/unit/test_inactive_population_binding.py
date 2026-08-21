from core.catalog_binding import apply_catalog_binding
from core.evidence_resolver import resolve_evidence_cell
from core.hard_guard import apply_hard_guard
from schemas.candidate import KosisCandidateSchema
from schemas.claim import ClaimSchema
from schemas.concept import StandardConceptSchema


def test_twenty_s_resting_population_uses_verified_official_coordinates() -> None:
    claim = ClaimSchema(
        claim_id="C", source_sentence="5월 20대 쉬었음 인구는 37만8000명이었다.",
        indicator="쉬었음 인구", value=378000, unit="명", time="2025년 5월",
        frequency="월", dimension={"age": "20대", "status": "쉬었음"},
        calculation="DIRECT_VALUE", parse_status="AUTO_OK",
    )
    concept = StandardConceptSchema(
        concept_id="C42", canonical_name="쉬었음 인구",
        standard_key="inactive_population_resting", matched_alias="쉬었음 인구",
        status="MATCHED",
    )
    candidate = KosisCandidateSchema(
        org_id="101", tbl_id="DT_1DA7147S", tbl_name="비경제활동인구 활동상태별",
        core_item_ids=["T50"], core_item_names=["비경제활동인구"],
        unit_names=["천명"], item_units={"T50": "천명"}, frequency="월",
        dimension_ids=["G", "M"], dimension_names=["연령계층별", "활동상태별"],
        dimension_members={"G": ["계", "15 - 29세", "20 - 29세"], "M": ["계", "쉬었음"]},
        dimension_member_codes={
            "G": {"계": "00", "15 - 29세": "75", "20 - 29세": "20"},
            "M": {"계": "000", "쉬었음": "905"},
        },
        start_period="202001", end_period="202512",
        metadata_status="OFFICIAL_METADATA_READY",
    )

    selected = apply_catalog_binding(claim, concept, [candidate])
    assert selected[0].source_stat_id == "OFFICIAL_RECURRING_DOMAIN_BINDING"
    assert apply_hard_guard(claim, selected[0]).passed
    cell = resolve_evidence_cell(claim, selected[0])
    assert cell.status == "CONFIRMED"
    assert cell.dimension_codes == {"G": "20", "M": "905"}
