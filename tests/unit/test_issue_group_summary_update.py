import csv

from core.issue_group_harness import (
    IssueGroup,
    build_issue_registry,
    record_group_run,
    write_issue_ledgers,
)


def test_group_summary_uses_latest_unique_claim_outcomes(tmp_path) -> None:
    records = build_issue_registry(
        [_row("C-001"), _row("C-002"), _row("C-003")]
    )
    write_issue_ledgers(records, tmp_path)
    results = [
        _after("C-001", "PASS", "KOSIS_PIPELINE_ELIGIBLE"),
        _after("C-002", "HUMAN_REVIEW", "CONTEXT_REQUIRED"),
        _after("C-003", "HUMAN_REVIEW", "STRUCTURAL_HOLD"),
    ]

    record_group_run(
        records,
        IssueGroup.CONTEXT,
        results,
        output_dir=tmp_path,
        run_id="context-001",
        code_version="code-v1",
        data_version="data-v1",
    )
    record_group_run(
        records,
        IssueGroup.CONTEXT,
        [results[0]],
        output_dir=tmp_path,
        run_id="context-002",
        code_version="code-v1",
        data_version="data-v1",
    )

    with (tmp_path / "group_summary.csv").open(
        encoding="utf-8-sig", newline=""
    ) as source:
        summary = {
            row["문제코드"]: row for row in csv.DictReader(source)
        }["CONTEXT"]
    assert summary["시도수"] == "3"
    assert summary["개선수"] == "1"
    assert summary["남은수"] == "2"


def _row(claim_id: str) -> dict[str, object]:
    return {
        "article_id": "A-001",
        "sentence_id": claim_id,
        "parent_claim_id": claim_id,
        "claim_id": claim_id,
        "source_sentence": "취업자는 증가했다.",
        "terminal_status": "HUMAN_REVIEW",
        "reason_code": "CONTEXT_REQUIRED",
        "claim": {"claim_id": claim_id},
        "slot_audit": {"entries": []},
        "stage_results": [],
        "official_resolution": None,
    }


def _after(claim_id: str, status: str, reason: str) -> dict[str, object]:
    return {
        "claim_id": claim_id,
        "status": status,
        "reason_code": reason,
        "stop_stage": "CLAIM_PARSE",
    }
