import json
from datetime import date
from pathlib import Path

from core.snapshot_asof import filter_rows_as_of
from core.verdict_engine import make_verdict


def test_goldset_milk_powder_growth_holds_when_latest_snapshot_is_after_article() -> None:
    snapshot = json.loads(
        Path("data/kosis_snapshots/value_DT_1J22112_B01A01402_202405_202505.json").read_text(encoding="utf-8")
    )
    usable = filter_rows_as_of(snapshot["response"], date(2025, 6, 26))

    assert any(row["PRD_DE"] == "202405" for row in usable)
    assert not any(row["PRD_DE"] == "202505" for row in usable)
    verdict = make_verdict("NEWS_B-030-A01", 3.4, [], None, tolerance=0.05)
    assert verdict.verdict == "UNDETERMINED"
    assert verdict.route_status == "HOLD"
    assert verdict.reason_code == "VALUE_UNAVAILABLE"
