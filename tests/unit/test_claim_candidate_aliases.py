from core.claim_candidate_aliases import normalize_claim_for_candidate
from schemas.candidate import KosisCandidateSchema
from schemas.claim import ClaimSchema


def test_education_shorthand_maps_only_to_confirmed_official_member() -> None:
    claim = ClaimSchema(
        claim_id="EDU-1", source_sentence="2024년 대졸 실업률은 3.1%였다.",
        indicator="실업률", value=3.1, unit="%", time="2024년", frequency="년",
        dimension={"학력": "대졸"}, calculation="DIRECT_VALUE", parse_status="AUTO_OK",
    )
    candidate = KosisCandidateSchema(
        org_id="101", tbl_id="DT_1DA7103S", tbl_name="교육정도별 실업률",
        dimension_members={"H1": ["계", "고졸", "대졸이상", "전문대졸"]},
        metadata_status="READY",
    )
    normalized = normalize_claim_for_candidate(claim, candidate)
    assert normalized.dimension == {"교육정도": "대졸이상"}