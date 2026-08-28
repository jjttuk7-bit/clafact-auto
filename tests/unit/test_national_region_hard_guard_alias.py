from core.hard_guard import apply_hard_guard
from schemas.candidate import KosisCandidateSchema
from schemas.claim import ClaimSchema


def _claim(region: str) -> ClaimSchema:
    return ClaimSchema(
        claim_id="C1",
        source_sentence=f"2025년 {region} 취업자는 2천만 명이다.",
        indicator="취업자 수",
        value=20_000_000,
        unit="명",
        time="2025",
        frequency="년",
        region=region,
        calculation="DIRECT_VALUE",
        parse_status="AUTO_OK",
    )


def _national_total_candidate() -> KosisCandidateSchema:
    return KosisCandidateSchema(
        org_id="101",
        tbl_id="DT_EMP_TOTAL",
        tbl_name="연간 취업자 총계",
        core_item_ids=["T1"],
        core_item_names=["취업자"],
        unit_names=["천명"],
        item_units={"T1": "천명"},
        frequency="년",
        start_period="2000",
        end_period="2026",
        metadata_status="OFFICIAL_METADATA_READY",
    )


def test_domestic_is_national_for_total_table_without_region_axis() -> None:
    assert apply_hard_guard(_claim("국내"), _national_total_candidate()).passed is True


def test_foreign_country_still_requires_region_axis() -> None:
    result = apply_hard_guard(_claim("아일랜드"), _national_total_candidate())
    assert result.passed is False
    assert "REGION_GRANULARITY_CONFLICT" in result.reject_codes
