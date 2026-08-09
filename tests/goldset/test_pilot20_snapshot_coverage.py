import json
from pathlib import Path


def test_reproducible_goldset_cases_have_explicit_snapshot_coverage_status() -> None:
    expected = json.loads(Path("tests/goldset/fixtures/pilot20_expected_routes.json").read_text(encoding="utf-8"))
    coverage = json.loads(Path("tests/goldset/fixtures/pilot20_snapshot_coverage.json").read_text(encoding="utf-8"))
    auto_ids = {row["claim_id"] for row in expected if row["expected_route"] == "AUTO"}

    assert set(coverage) == auto_ids
    assert all(status in {"COVERED", "PENDING"} for status in coverage.values())
