from __future__ import annotations

import csv
import json

from tools.run_issue_group_harness import main


def test_classify_command_writes_reconciled_ledgers_without_runtime(tmp_path) -> None:
    baseline = tmp_path / "baseline.jsonl"
    baseline.write_text(
        "\n".join(
            json.dumps(row, ensure_ascii=False)
            for row in (
                _baseline_row("C-001", "CONTEXT_REQUIRED"),
                _baseline_row("C-002", "NO_HARD_GUARD_CANDIDATE"),
            )
        )
        + "\n",
        encoding="utf-8",
    )
    output = tmp_path / "harness"

    exit_code = main(["classify", str(baseline), str(output)])

    assert exit_code == 0
    with (output / "claim_issue_master.csv").open(
        encoding="utf-8-sig", newline=""
    ) as source:
        rows = list(csv.DictReader(source))
    assert len(rows) == 2
    assert {row["대표문제"] for row in rows} == {"CONTEXT", "HARD_GUARD"}


def _baseline_row(claim_id: str, reason: str) -> dict[str, object]:
    return {
        "article_id": "A-001",
        "sentence_id": claim_id,
        "parent_claim_id": claim_id,
        "claim_id": claim_id,
        "source_sentence": "취업자는 10만 명 증가했다.",
        "terminal_status": "HUMAN_REVIEW" if reason == "CONTEXT_REQUIRED" else "HOLD",
        "reason_code": reason,
        "claim": {"claim_id": claim_id},
        "slot_audit": {"entries": []},
        "stage_results": [],
        "official_resolution": None,
    }
