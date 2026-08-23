from core.calculation_planner import build_calculation_plan
from schemas.candidate import KosisCandidateSchema
from schemas.claim import ClaimSchema
from schemas.evidence import EvidenceCellSchema


def test_record_plan_rejects_claim_after_matching_official_end_period() -> None:
    claim = ClaimSchema(
        claim_id="record-after-end",
        source_sentence="고용률은 2025년 6월 역대 최대였다.",
        calculation="RECORD_HIGH",
        comparison={"type": "RECORD_HIGH"},
        parse_status="AUTO_OK",
    )
    current = EvidenceCellSchema(
        org_id="101",
        tbl_id="DT_EMP",
        itm_id="T",
        prd_se="월",
        prd_de="2025-06",
        canonical_key="DT_EMP|2025-06",
        status="CONFIRMED",
    )
    candidate = KosisCandidateSchema(
        org_id="101",
        tbl_id="DT_EMP",
        tbl_name="고용률",
        frequency="월|년",
        period_ranges={
            "월": {"start_period": "2020.01", "end_period": "2024.12"},
            "년": {"start_period": "2020", "end_period": "2025"},
        },
        metadata_status="OFFICIAL_METADATA_READY",
    )

    assert build_calculation_plan(claim, current, candidate) is None
