from core.verdict_engine import make_verdict


def test_match_within_tolerance() -> None:
    assert make_verdict("C1", 70.0, [70.01], 70.01, tolerance=0.02).verdict == "MATCH"


def test_mismatch_outside_tolerance() -> None:
    assert make_verdict("C1", 70.0, [71.0], 71.0, tolerance=0.02).verdict == "MISMATCH"


def test_missing_value_routes_hold() -> None:
    result = make_verdict("C1", 70.0, [], None)
    assert result.verdict == "UNDETERMINED"
    assert result.route_status == "HOLD"
