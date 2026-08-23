from core.calculation_planner import build_calculation_plan
from schemas.candidate import KosisCandidateSchema
from schemas.claim import ClaimSchema
from schemas.evidence import EvidenceCellSchema


def _claim(*, frequency: str = "월") -> ClaimSchema:
    return ClaimSchema(
        claim_id="record-period-range",
        source_sentence="15~64세 고용률은 70.3%로 6월 기준 역대 최대였다.",
        indicator="고용률",
        value=70.3,
        unit="%",
        time="2025년 6월",
        frequency=frequency,
        population="15~64세",
        calculation="RECORD_HIGH",
        comparison={"type": "RECORD_HIGH"},
        parse_status="AUTO_OK",
    )


def _current(*, prd_se: str = "월", prd_de: str = "2025-06") -> EvidenceCellSchema:
    return EvidenceCellSchema(
        org_id="101",
        tbl_id="DT_EMP",
        itm_id="T90",
        prd_se=prd_se,
        prd_de=prd_de,
        canonical_key=f"DT_EMP|PRD_DE={prd_de}",
        status="CONFIRMED",
    )


def test_monthly_record_plan_uses_only_official_monthly_range() -> None:
    candidate = KosisCandidateSchema(
        org_id="101",
        tbl_id="DT_EMP",
        tbl_name="연령별 고용률",
        frequency="월|분기|년",
        start_period="1999 3/4",
        period_ranges={
            "월": {"start_period": "1999.06", "end_period": "2026.07"},
            "분기": {"start_period": "1999 3/4", "end_period": "2026 2/4"},
            "년": {"start_period": "2000", "end_period": "2025"},
        },
        metadata_status="OFFICIAL_METADATA_READY",
    )

    plan = build_calculation_plan(_claim(), _current(), candidate)

    assert plan is not None
    periods = [cell.prd_de for cell in plan.required_cells]
    assert periods[0] == "1999-06"
    assert periods[-1] == "2025-06"
    assert len(periods) == 27


def test_mixed_frequency_candidate_without_exact_ranges_is_not_inferred() -> None:
    candidate = KosisCandidateSchema(
        org_id="101",
        tbl_id="DT_EMP",
        tbl_name="연령별 고용률",
        frequency="월|분기|년",
        start_period="1999.06",
        metadata_status="OFFICIAL_METADATA_READY",
    )

    assert build_calculation_plan(_claim(), _current(), candidate) is None


def test_legacy_single_frequency_candidate_keeps_scalar_period_support() -> None:
    candidate = KosisCandidateSchema(
        org_id="101",
        tbl_id="DT_YEAR",
        tbl_name="연간 고용률",
        frequency="년",
        start_period="2022",
        metadata_status="OFFICIAL_METADATA_READY",
    )
    claim = _claim(frequency="년").model_copy(update={
        "source_sentence": "고용률은 2024년 역대 최대였다.",
        "time": "2024년",
    })

    plan = build_calculation_plan(claim, _current(prd_se="년", prd_de="2024"), candidate)

    assert plan is not None
    assert [cell.prd_de for cell in plan.required_cells] == ["2022", "2023", "2024"]


def test_monthly_evidence_cannot_use_only_annual_official_range() -> None:
    candidate = KosisCandidateSchema(
        org_id="101",
        tbl_id="DT_EMP",
        tbl_name="연령별 고용률",
        frequency="월|년",
        period_ranges={"년": {"start_period": "2000", "end_period": "2025"}},
        metadata_status="OFFICIAL_METADATA_READY",
    )

    assert build_calculation_plan(_claim(), _current(), candidate) is None
