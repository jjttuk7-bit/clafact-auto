import json

from core.operations_artifacts import load_operations_artifacts


def test_loads_result_rows_report_and_review_queue_without_writing(tmp_path) -> None:
    results = tmp_path / "results.jsonl"
    results.write_text(json.dumps({"claim_id":"C1","route_status":"HOLD"}) + "\n", encoding="utf-8")
    report = tmp_path / "coverage.json"
    report.write_text(json.dumps({"total_records":1}), encoding="utf-8")
    queue = tmp_path / "queue.jsonl"
    queue.write_text(json.dumps({"source_key":"A1:S1"}) + "\n", encoding="utf-8")
    artifact = load_operations_artifacts(results, report, queue)
    assert artifact.results[0]["claim_id"] == "C1"
    assert artifact.coverage["total_records"] == 1
    assert artifact.review_queue[0]["source_key"] == "A1:S1"
