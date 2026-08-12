import json
from pathlib import Path

from core.claim_admissibility_queue import build_admissibility_records
from schemas.claim_registry import ClaimRegistryRecord


def test_builds_one_admissibility_record_per_original_parse_hold() -> None:
    record = ClaimRegistryRecord.model_validate({
        "article_id": "A1", "sentence_id": "1", "source_ref": "gold_standard_v1",
        "claim": {"claim_id": "A1_1", "source_sentence": "지난달 3% 올랐다.", "indicator": "물가", "value": 3, "unit": "%", "parse_status": "HOLD"},
    })
    output = build_admissibility_records([record], {"A1_1": {"route_status": "HOLD", "reason_code": "'지난달'의 기준 시점이 제공되지 않아 시간을 확정할 수 없음"}})

    assert output == [{
        "claim_id": "A1_1", "article_id": "A1", "sentence_id": "1", "source_ref": "gold_standard_v1",
        "admissibility_route": "CONTEXT_REQUIRED", "admissibility_reason_code": "RELATIVE_TIME_UNRESOLVED",
        "reparse_route_status": "HOLD", "reparse_reason": "'지난달'의 기준 시점이 제공되지 않아 시간을 확정할 수 없음",
        "source_sentence": "지난달 3% 올랐다.", "slots": {"indicator": "물가", "value": 3.0, "unit": "%", "time": None, "frequency": None, "region": None, "population": None, "dimension": None, "comparison": None, "calculation": None, "condition": None, "source_hint": None, "parse_status": "HOLD", "parse_reason": None},
    }]
