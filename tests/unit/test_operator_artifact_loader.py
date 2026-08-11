import json
from pathlib import Path


def test_load_operator_run_reads_report_results_and_profile_queue(tmp_path: Path) -> None:
    from core.operator_artifact_loader import load_operator_run

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "coverage_and_e2e_report.json").write_text(json.dumps({"route_counts": {"HOLD": 2}}), encoding="utf-8")
    (run_dir / "claim_verification_results.jsonl").write_text('{"claim_id":"c1","route_status":"HOLD"}\n', encoding="utf-8")
    (run_dir / "profile_review_priority_queue.json").write_text('[{"priority_rank":1,"claim_count":2}]', encoding="utf-8")

    artifact = load_operator_run(run_dir)

    assert artifact.report["route_counts"] == {"HOLD": 2}
    assert artifact.results[0]["claim_id"] == "c1"
    assert artifact.profile_queue[0]["priority_rank"] == 1
