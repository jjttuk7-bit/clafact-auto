import json
from datetime import date
from pathlib import Path

from core.calculator import calculate
from core.snapshot_asof import filter_rows_as_of
from core.verdict_engine import make_verdict
from schemas.evidence import CalculationPlan


def test_goldset_birth_growth_is_deterministic_but_holds_after_asof_guard() -> None:
    snapshot = json.loads(
        Path("data/kosis_snapshots/value_DT_1B8000G_births_202404_202504.json").read_text(encoding="utf-8")
    )
    rows = {row["PRD_DE"]: row for row in snapshot["response"]}
    growth = calculate(CalculationPlan(calculation_type="GROWTH_RATE"), [float(rows["202504"]["DT"]), float(rows["202404"]["DT"])])

    assert round(growth, 3) == 9.193
    assert not any(row["PRD_DE"] == "202504" for row in filter_rows_as_of(snapshot["response"], date(2025, 6, 25)))
    verdict = make_verdict("NEWS_B-003-A01", 8.7, [], None, tolerance=0.05)
    assert verdict.route_status == "HOLD"
