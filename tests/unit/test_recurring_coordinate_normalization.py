from datetime import date

from core.claim_time_resolver import resolve_relative_time
from core.evidence_resolver import resolve_evidence_cell
from schemas.candidate import KosisCandidateSchema
from schemas.claim import ClaimSchema


def test_resolves_last_year_named_month_from_article_date():
    claim = ClaimSchema(
        claim_id="B", source_sentence="작년 11월 출생아 수는 2만95명이었다.",
        indicator="출생아 수", value=20095, unit="명", time="작년 11월",
        frequency="월", parse_status="AUTO_OK",
    )
    result = resolve_relative_time(claim, date(2025, 1, 22))
    assert result.time == "2024년 11월"
    assert result.frequency == "월"


def test_bound_aggregate_item_suffix_matches_indicator():
    claim = ClaimSchema(
        claim_id="R", source_sentence="2025년 벼 재배면적은 67만8000ha다.",
        indicator="벼 재배 면적", value=678000, unit="ha", time="2025년",
        frequency="년", dimension={"작물":"벼"}, parse_status="AUTO_OK",
    )
    candidate = KosisCandidateSchema(
        org_id="101", tbl_id="DT_1ET0012", tbl_name="노지 식량작물 재배면적",
        core_item_ids=["T06"], core_item_names=["벼계"], unit_names=["헥타르"],
        frequency="년", dimension_ids=["C1"], dimension_names=["시도별"],
        dimension_members={"C1":["전국"]}, dimension_member_codes={"C1":{"전국":"00"}},
        metadata_status="OFFICIAL_METADATA_READY",
    )
    assert resolve_evidence_cell(claim, candidate).status == "CONFIRMED"
