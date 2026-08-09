"""Goldset E2E routing helpers."""
from typing import Any

def expected_route(record: dict[str, Any]) -> str:
    return "AUTO" if record.get("KOSIS_재현_상태") == "KOSIS 재현 가능" else "HOLD"

def gold_snapshot_requirements(record: dict[str, Any]) -> dict[str, str] | None:
    if expected_route(record) != "AUTO":
        return None
    return {"table_id": str(record["gold_table_id"]), "coordinate": str(record["gold_coordinate"]), "value": str(record["gold_evidence_value"])}
