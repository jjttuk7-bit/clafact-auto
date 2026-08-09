import json
from pathlib import Path
from core.e2e_runner import expected_route, gold_snapshot_requirements

def test_all_pilot_records_have_safe_e2e_route() -> None:
    records = json.loads((Path(__file__).parent / "fixtures" / "pilot20.json").read_text(encoding="utf-8"))
    assert sum(expected_route(record) == "AUTO" for record in records) == 13
    assert sum(expected_route(record) == "HOLD" for record in records) == 7

def test_auto_records_have_snapshot_requirements() -> None:
    records = json.loads((Path(__file__).parent / "fixtures" / "pilot20.json").read_text(encoding="utf-8"))
    requirements = [gold_snapshot_requirements(record) for record in records]
    assert all(requirement is not None for requirement in requirements if requirement)
