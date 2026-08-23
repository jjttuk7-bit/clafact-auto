from datetime import date

from core.calculation_planner import build_calculation_plan
from core.claim_time_resolver import resolve_relative_time
from schemas.candidate import KosisCandidateSchema
from schemas.claim import ClaimSchema
from schemas.evidence import EvidenceCellSchema


def _claim(**updates) -> ClaimSchema:
    payload = {
        "claim_id": "record-month",
        "source_sentence": "15~64\uc138 \uace0\uc6a9\ub960\uc740 70.3%\ub85c 6\uc6d4 \uae30\uc900 \uc5ed\ub300 \ucd5c\ub300\uc600\ub2e4.",
        "indicator": "\uace0\uc6a9\ub960", "value": 70.3, "unit": "%", "time": "6\uc6d4", "frequency": "\uc6d4",
        "population": "15~64\uc138", "calculation": "RECORD_HIGH",
        "comparison": {"type": "RECORD_HIGH"}, "parse_status": "AUTO_OK",
    }
    payload.update(updates)
    return ClaimSchema(**payload)


def test_resolves_bare_named_month_to_most_recent_month_not_after_article() -> None:
    current_year = resolve_relative_time(_claim(), date(2025, 7, 16))
    previous_year = resolve_relative_time(_claim(time="12\uc6d4"), date(2025, 1, 16))

    assert current_year.time == "2025\ub144 6\uc6d4"
    assert previous_year.time == "2024\ub144 12\uc6d4"


def test_month_basis_record_plan_compares_only_same_month_across_years() -> None:
    claim = _claim(time="2025\ub144 6\uc6d4")
    current = EvidenceCellSchema(
        org_id="101", tbl_id="DT_EMP", itm_id="T90",
        dimension_members={"G": "15 - 64\uc138"}, dimension_codes={"G": "63"},
        prd_se="\uc6d4", prd_de="2025-06", unit="%",
        canonical_key="ORG=101|TBL=DT_EMP|ITM=T90|G:15-64|PRD_DE=2025-06",
        status="CONFIRMED",
    )
    candidate = KosisCandidateSchema(
        org_id="101", tbl_id="DT_EMP", tbl_name="\uc5f0\ub839\ubcc4 \uace0\uc6a9\ub960",
        core_item_ids=["T90"], core_item_names=["\uace0\uc6a9\ub960"],
        dimension_ids=["G"], dimension_names=["\uc5f0\ub839\uacc4\uce35\ubcc4"],
        dimension_members={"G": ["15 - 64\uc138"]},
        dimension_member_codes={"G": {"15 - 64\uc138": "63"}},
        unit_names=["%"], item_units={"T90": "%"}, frequency="\uc6d4|\ubd84\uae30|\ub144",
        start_period="1999.06", end_period="2026.07", metadata_status="OFFICIAL_METADATA_READY",
    )

    plan = build_calculation_plan(claim, current, candidate)

    assert plan is not None
    periods = [cell.prd_de for cell in plan.required_cells]
    assert periods[0] == "1999-06"
    assert periods[-1] == "2025-06"
    assert len(periods) == 27
    assert all(period.endswith("-06") for period in periods)


def test_same_month_periods_start_after_the_official_start_month() -> None:
    from core.record_periods import enumerate_same_month_periods

    assert enumerate_same_month_periods("2020.10", "2025-06") == [
        "2021-06", "2022-06", "2023-06", "2024-06", "2025-06",
    ]


def test_same_month_periods_reject_non_monthly_start_metadata() -> None:
    from core.record_periods import enumerate_same_month_periods

    assert enumerate_same_month_periods("1999 3/4", "2025-06") is None
