import json
from datetime import date
from pathlib import Path

from core.calculator import calculate
from core.snapshot_asof import filter_rows_as_of
from core.verdict_engine import make_verdict
from schemas.evidence import CalculationPlan


def test_goldset_milk_powder_growth_matches_curated_official_asof_snapshot() -> None:
    snapshot = json.loads(Path("data/kosis_snapshots/official_goldset_asof_v3.json").read_text(encoding="utf-8"))
    rows = filter_rows_as_of(snapshot["records"], date(2025, 6, 26))
    values = {row["period"]: row["value"] for row in rows}
    growth = calculate(CalculationPlan(calculation_type="GROWTH_RATE"), [values["202505"], values["202405"]])
    verdict = make_verdict("NEWS_B-030-A01", 3.4, [values["202405"], values["202505"]], growth, tolerance=0.05)

    assert round(growth, 1) == 3.4
    assert verdict.verdict == "MATCH"
    assert verdict.route_status == "AUTO"
from datetime import date
from pathlib import Path

from core.kosis_fetcher import OfficialValueFetcher
from schemas.evidence import EvidenceCellSchema


def test_official_value_fetcher_reads_goldset_asof_snapshot() -> None:
    cell = EvidenceCellSchema(
        org_id="101", tbl_id="DT_1J22112", itm_id="T", prd_se="M", prd_de="202505",
        canonical_key="unused", status="CONFIRMED",
    )
    result = OfficialValueFetcher([Path("data/kosis_snapshots/official_goldset_asof_v3.json")]).fetch(
        cell, article_date=date(2025, 6, 26)
    )

    assert result.status == "SUCCESS"
    assert result.value == 109.67
    assert result.source == "SNAPSHOT"
