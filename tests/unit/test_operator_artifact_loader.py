import json
from pathlib import Path


def test_load_operator_run_exposes_generic_review_queue(tmp_path: Path) -> None:
    from core.operator_artifact_loader import load_operator_run

    run_dir = tmp_path / "run"
    review_dir = run_dir / "review_queues"
    review_dir.mkdir(parents=True)
    (run_dir / "coverage_report.json").write_text(
        json.dumps({"route_counts": {"HOLD": 1}}), encoding="utf-8"
    )
    (run_dir / "e2e_results.jsonl").write_text(
        '{"claim_id":"c1","route_status":"HOLD"}\n', encoding="utf-8"
    )
    (review_dir / "parse.jsonl").write_text(
        '{"claim_id":"c2","reason_code":"CLAIM_PARSE_UNCERTAIN"}\n',
        encoding="utf-8",
    )
    (review_dir / "summary.json").write_text(
        json.dumps({"queue_counts": {"parse": 1}}), encoding="utf-8"
    )

    artifact = load_operator_run(run_dir)

    assert artifact.results[0]["claim_id"] == "c1"
    assert artifact.review_queue == [{"claim_id": "c2", "reason_code": "CLAIM_PARSE_UNCERTAIN"}]
    assert artifact.review_summary["queue_counts"] == {"parse": 1}
