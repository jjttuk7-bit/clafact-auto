from core.calculator import calculate
from core.cpi_growth_resolver import resolve_cpi_growth_plan
from core.growth_execution import execute_growth_plan
from core.growth_verdict import make_cpi_growth_verdict
from core.kosis_fetcher import OfficialValueFetcher
from datetime import date
from pathlib import Path
from schemas.claim import ClaimSchema


def _claim(**updates: object) -> ClaimSchema:
    values = {
        "claim_id": "cpi-detail-1",
        "source_sentence": "structured output source",
        "indicator": "배추",
        "value": -34.5,
        "unit": "%",
        "time": "2025년 10월",
        "frequency": "월",
        "calculation": "GROWTH_RATE",
        "parse_status": "AUTO_OK",
    }
    values.update(updates)
    return ClaimSchema(**values)


def test_resolves_registered_cpi_item_to_current_and_prior_year_cells() -> None:
    plan = resolve_cpi_growth_plan(_claim())

    assert plan is not None
    assert plan.calculation_plan.calculation_type == "GROWTH_RATE"
    assert [cell.prd_de for cell in plan.calculation_plan.required_cells] == ["202510", "202410"]
    assert all(cell.tbl_id == "DT_1J22112" and cell.itm_id == "T" for cell in plan.calculation_plan.required_cells)
    assert all(cell.dimension_codes == {"C1": "T10", "C2": "A02A01701"} for cell in plan.calculation_plan.required_cells)


def test_growth_plan_uses_python_calculation_for_two_official_values() -> None:
    plan = resolve_cpi_growth_plan(_claim())

    assert plan is not None
    assert round(calculate(plan.calculation_plan, [136.62, 208.57]), 1) == -34.5


def test_unregistered_indicator_never_receives_a_coordinate() -> None:
    assert resolve_cpi_growth_plan(_claim(indicator="가공식품")) is None


def test_registered_cpi_detail_percent_claim_uses_growth_plan_when_extractor_labels_direct_value() -> None:
    plan = resolve_cpi_growth_plan(_claim(calculation="DIRECT_VALUE"))

    assert plan is not None
    assert plan.calculation_plan.calculation_type == "GROWTH_RATE"


def test_executes_growth_plan_from_two_official_snapshot_values() -> None:
    plan = resolve_cpi_growth_plan(_claim())

    assert plan is not None
    result = execute_growth_plan(
        plan.calculation_plan,
        OfficialValueFetcher([Path("data/kosis_snapshots/official_goldset_v3_news_b023.json")]),
        date(2025, 11, 4),
    )

    assert result.status == "SUCCESS"
    assert result.values == [136.62, 208.57]
    assert round(result.calculated_value or 0, 1) == -34.5


def test_makes_auto_verdict_from_registered_cpi_growth_plan() -> None:
    verdict = make_cpi_growth_verdict(
        _claim(),
        date(2025, 11, 4),
        OfficialValueFetcher([Path("data/kosis_snapshots/official_goldset_v3_news_b023.json")]),
    )

    assert verdict is not None
    assert verdict.verdict == "MATCH"
    assert verdict.route_status == "AUTO"
    assert len(verdict.evidence_cells) == 2


def test_returns_none_when_claim_has_no_registered_growth_coordinate() -> None:
    assert make_cpi_growth_verdict(_claim(indicator="가공식품"), date(2025, 11, 4), OfficialValueFetcher([])) is None


def test_resolves_registered_cpi_item_alias_without_fuzzy_matching() -> None:
    plan = resolve_cpi_growth_plan(_claim(indicator="배추 물가"))

    assert plan is not None
    assert plan.calculation_plan.required_cells[0].dimension_codes["C2"] == "A02A01701"
