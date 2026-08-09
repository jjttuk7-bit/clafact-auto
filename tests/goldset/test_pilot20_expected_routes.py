import json
from pathlib import Path


def test_pilot20_has_complete_expected_route_contract() -> None:
    records = json.loads(Path("tests/goldset/fixtures/pilot20.json").read_text(encoding="utf-8"))
    expected = json.loads(Path("tests/goldset/fixtures/pilot20_expected_routes.json").read_text(encoding="utf-8"))
    routes = {row["claim_id"]: row for row in expected}

    assert len(records) == 20
    assert set(routes) == {row["claim_id"] for row in records}
    assert {row["expected_route"] for row in expected} == {"AUTO", "HOLD"}
    assert sum(row["expected_route"] == "AUTO" for row in expected) == 13
    assert sum(row["expected_route"] == "HOLD" for row in expected) == 7


def test_pilot20_expected_route_agrees_with_goldset_reproducibility() -> None:
    records = json.loads(Path("tests/goldset/fixtures/pilot20.json").read_text(encoding="utf-8"))
    expected = {row["claim_id"]: row for row in json.loads(Path("tests/goldset/fixtures/pilot20_expected_routes.json").read_text(encoding="utf-8"))}

    for record in records:
        route = expected[record["claim_id"]]
        if record["KOSIS_재현_상태"] == "KOSIS 재현 가능":
            assert route["expected_route"] == "AUTO"
            assert route["expected_verdict"] == "MATCH"
        else:
            assert route["expected_route"] == "HOLD"
            assert route["expected_verdict"] == "UNDETERMINED"
