from core.hard_guard import apply_hard_guard
from schemas.candidate import KosisCandidateSchema
from schemas.claim import ClaimSchema


def test_binding_table_scope_consumes_fifteen_plus_age_requirement() -> None:
    claim = ClaimSchema(
        claim_id="EMP-SCOPE-GUARD",
        source_sentence="2025년 9월 15세 이상 취업자는 2915만4000명이다.",
        indicator="취업자", value=29_154_000, unit="명", time="2025년 9월",
        frequency="월", population="15세 이상", dimension={"age": "15세 이상"},
        calculation="DIRECT_VALUE", parse_status="AUTO_OK",
    )
    candidate = KosisCandidateSchema(
        org_id="101", tbl_id="DT_1DA7001S", tbl_name="경제활동인구 총괄",
        core_item_ids=["T30"], core_item_names=["취업자"],
        dimension_ids=["B"], dimension_names=["성별"],
        dimension_members={"B": ["계"]}, dimension_member_codes={"B": {"계": "0"}},
        unit_names=["천명"], item_units={"T30": "천명"}, frequency="월",
        start_period="1982.07", end_period="2026.07",
        source_stat_id="OFFICIAL_RECURRING_DOMAIN_BINDING",
        binding_scope_terms=["15세 이상", "15세 이상 전체"],
        metadata_status="OFFICIAL_METADATA_READY",
    )

    result = apply_hard_guard(claim, candidate)

    assert result.passed is True
    assert result.reject_codes == []

