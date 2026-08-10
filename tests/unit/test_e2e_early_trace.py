from core.e2e_batch_runner import run_e2e_batch
from schemas.claim_registry import ClaimRegistryRecord


def test_e2e_batch_attaches_trace_when_concept_is_missing() -> None:
    record = ClaimRegistryRecord.model_validate(
        {
            "article_id": "A1",
            "sentence_id": "S1",
            "source_ref": "fixture",
            "claim": {
                "claim_id": "C1",
                "source_sentence": "2025년 10월 배추 물가는 전년 동월 대비 34.5% 하락했다.",
                "parse_status": "AUTO_OK",
            },
        }
    )

    result = run_e2e_batch([record], [], {})[0]

    assert result["route_status"] == "HOLD"
    assert result["execution_trace"]["events"][-1]["stage"] == "SEMANTIC_MATCH"