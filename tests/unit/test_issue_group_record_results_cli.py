from __future__ import annotations

import csv
import json

from tools.run_issue_group_harness import main


def test_record_results_replays_saved_results_without_executor(tmp_path) -> None:
    baseline = tmp_path / "baseline.jsonl"
    baseline.write_text(json.dumps(_baseline()) + "\n", encoding="utf-8")
    output = tmp_path / "output"
    assert main(["classify", str(baseline), str(output)]) == 0
    saved = tmp_path / "saved.jsonl"
    saved.write_text(
        json.dumps(
            {
                "claim_id": "C-001",
                "status": "PASS",
                "reason_code": "KOSIS_PIPELINE_ELIGIBLE",
                "stop_stage": "CLAIM_PARSE",
                "executed_stages": ["CLAIM_SPLIT", "CLAIM_PARSE"],
                "official_lookup_attempted": False,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    exit_code = main(
        [
            "record-results",
            str(baseline),
            str(saved),
            str(output),
            "--group",
            "CONTEXT",
            "--run-id",
            "context-001",
            "--code-version",
            "code-v1",
        ]
    )

    assert exit_code == 0
    with (output / "group_summary.csv").open(
        encoding="utf-8-sig", newline=""
    ) as source:
        summary = {
            row["문제코드"]: row for row in csv.DictReader(source)
        }["CONTEXT"]
    assert summary["시도수"] == "1"
    assert summary["개선수"] == "1"
    assert summary["남은수"] == "0"


def _baseline() -> dict[str, object]:
    return {
        "article_id": "A-001",
        "sentence_id": "1",
        "parent_claim_id": "C-001",
        "claim_id": "C-001",
        "source_sentence": "취업자는 증가했다.",
        "terminal_status": "HUMAN_REVIEW",
        "reason_code": "CONTEXT_REQUIRED",
        "claim": {"claim_id": "C-001"},
        "slot_audit": {"entries": []},
        "stage_results": [],
        "official_resolution": None,
    }
