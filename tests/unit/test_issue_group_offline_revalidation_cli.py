import csv
import json

from tools.run_issue_group_harness import main


def test_record_results_can_revalidate_saved_children_with_registry_dates(tmp_path) -> None:
    baseline = tmp_path / "baseline.jsonl"
    baseline.write_text(json.dumps({
        "article_id": "A1", "sentence_id": "1", "parent_claim_id": "C1",
        "claim_id": "C1", "source_sentence": "The value was 1419 and set a record high.",
        "terminal_status": "HUMAN_REVIEW", "reason_code": "CONTEXT_REQUIRED",
        "claim": {"claim_id": "C1"}, "slot_audit": {"entries": []},
        "stage_results": [], "official_resolution": None,
    }) + "\n", encoding="utf-8")
    registry = tmp_path / "registry.jsonl"
    registry.write_text(json.dumps({
        "article_id": "A1", "sentence_id": "1", "article_published_at": "2025-01-02",
        "source_ref": "test", "claim": {
            "claim_id": "C1", "source_sentence": "The value was 1419 and set a record high.",
            "indicator": "export value", "value": 1419, "unit": "USD 100m",
            "time": "2024", "frequency": "annual", "region": None,
            "population": None, "dimension": None, "comparison": {"type": "RECORD_HIGH"},
            "calculation": "DIRECT_VALUE", "condition": None, "source_hint": None,
            "parse_status": "AUTO_OK", "parse_reason": None,
        },
    }) + "\n", encoding="utf-8")
    saved = tmp_path / "saved.jsonl"
    saved.write_text(json.dumps({
        "claim_id": "C1", "status": "PASS", "reason_code": "KOSIS_PIPELINE_ELIGIBLE",
        "stop_stage": "CLAIM_PARSE", "executed_stages": ["CLAIM_SPLIT", "CLAIM_PARSE"],
        "official_lookup_attempted": False, "children": [{
            "claim_id": "C1", "admission_route": "KOSIS_PIPELINE_ELIGIBLE",
            "twelve_slot_complete": True,
            "claim": json.loads(registry.read_text(encoding="utf-8"))["claim"],
        }],
    }) + "\n", encoding="utf-8")
    output = tmp_path / "output"

    exit_code = main([
        "record-results", str(baseline), str(saved), str(output),
        "--group", "CONTEXT", "--run-id", "context-safe",
        "--registry-path", str(registry),
    ])

    assert exit_code == 0
    with (output / "runs" / "context-safe_children.csv").open(
        encoding="utf-8-sig", newline=""
    ) as source:
        child = next(csv.DictReader(source))
    assert child["재입장경로"] != "KOSIS_PIPELINE_ELIGIBLE"
    assert child["재분류사유"] == "RECORD_COMPARISON_REQUIRES_SEPARATE_CLAIM"
    normalized = json.loads((output / "runs" / "context-safe.jsonl").read_text(encoding="utf-8"))
    assert normalized["children"][0]["admission_route"] != "KOSIS_PIPELINE_ELIGIBLE"
    assert normalized["children"][0]["recovery_audit"]["offline_revalidated"] is True
