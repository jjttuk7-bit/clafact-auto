from core.evidence_resolver import resolve_evidence_cell
from core.hard_guard import apply_hard_guard
from core.kosis_query_spec_compiler import compile_kosis_query_spec
from schemas.candidate import KosisCandidateSchema
from schemas.claim import ClaimSchema


def _claim(region: str) -> ClaimSchema:
    return ClaimSchema(
        claim_id="C1",
        source_sentence=f"지난달 {region} 제조업 취업자는 441만4000명이다.",
        indicator="취업자 수",
        value=4_414_000,
        unit="명",
        time="2025-07",
        frequency="월",
        region=region,
        calculation="DIRECT_VALUE",
        parse_status="AUTO_OK",
    )


def _candidate() -> KosisCandidateSchema:
    return KosisCandidateSchema(
        org_id="101",
        tbl_id="DT_EMP",
        tbl_name="산업별 취업자",
        core_item_ids=["T1"],
        core_item_names=["취업자"],
        dimension_ids=["R"],
        dimension_names=["지역별"],
        dimension_members={"R": ["전국"]},
        dimension_member_codes={"R": {"전국": "00"}},
        unit_names=["천명"],
        item_units={"T1": "천명"},
        frequency="월",
        start_period="2000.01",
        end_period="2026.07",
        metadata_status="OFFICIAL_METADATA_READY",
    )


def test_domestic_region_is_a_source_grounded_national_alias() -> None:
    claim = _claim("국내")

    assert apply_hard_guard(claim, _candidate()).passed is True
    cell = resolve_evidence_cell(claim, _candidate())
    assert cell.status == "CONFIRMED"
    assert cell.dimension_members == {"R": "전국"}
    assert cell.dimension_codes == {"R": "00"}
    assert compile_kosis_query_spec(claim, article_date=None).geography_scope == "NATIONAL"


def test_foreign_country_is_not_treated_as_national_alias() -> None:
    claim = _claim("아일랜드")

    cell = resolve_evidence_cell(claim, _candidate())
    assert cell.status == "UNRESOLVED"
    assert compile_kosis_query_spec(claim, article_date=None).geography_scope == "COUNTRY"
