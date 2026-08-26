from core.claim_candidate_aliases import normalize_claim_for_candidate
from schemas.candidate import KosisCandidateSchema
from schemas.claim import ClaimSchema


def test_age_population_suffix_maps_only_to_an_official_member():
    claim = ClaimSchema(
        claim_id="claim_age", source_sentence="65세 이상 인구의 고용률은 40.4%였다.",
        indicator="고용률", value=40.4, unit="%", time="2025년 4월",
        frequency="월", population="65세 이상 인구", calculation="DIRECT_VALUE",
        parse_status="AUTO_OK",
    )
    candidate = KosisCandidateSchema(
        org_id="101", tbl_id="AGE", tbl_name="연령별 고용률",
        core_item_ids=["T90"], core_item_names=["고용률"],
        dimension_ids=["G"], dimension_names=["연령계층별"],
        dimension_members={"G": ["15 - 29세", "65세 이상"]},
        dimension_member_codes={"G": {"15 - 29세": "75", "65세 이상": "602"}},
        unit_names=["%"], item_units={"T90": "%"}, frequency="월",
        metadata_status="OFFICIAL_METADATA_READY",
    )
    assert normalize_claim_for_candidate(claim, candidate).population == "65세 이상"
    unresolved = candidate.model_copy(update={"dimension_members": {"G": ["15 - 29세"]}})
    assert normalize_claim_for_candidate(claim, unresolved).population == "65세 이상 인구"
