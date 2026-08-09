import json
from pathlib import Path


FIXTURE = Path(__file__).parent / "fixtures" / "pilot20.json"


def test_pilot20_has_twenty_fixed_gold_records() -> None:
    records = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert len(records) == 20
    assert all(record["claim_id"] and record["sentence_text"] for record in records)


def test_reproducible_gold_records_have_kosis_evidence_contract() -> None:
    records = json.loads(FIXTURE.read_text(encoding="utf-8"))
    reproducible = [r for r in records if r["KOSIS_재현_상태"] == "KOSIS 재현 가능"]
    assert len(reproducible) == 13
    assert all(r["gold_table_id"] and r["gold_coordinate"] and r["gold_evidence_value"] for r in reproducible)


def test_unreproducible_records_are_preserved_as_not_comparable() -> None:
    records = json.loads(FIXTURE.read_text(encoding="utf-8"))
    unreproducible = [r for r in records if r["KOSIS_재현_상태"] == "KOSIS 재현 불가"]
    assert len(unreproducible) == 7
    assert all(r["gold_verdict_standard"] == "not_comparable" for r in unreproducible)
