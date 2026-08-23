import csv

from core.issue_group_executor import write_context_child_csv
from core.issue_group_harness import (
    IssueGroup,
    build_issue_registry,
    compare_result,
    record_group_run,
    write_issue_ledgers,
)


def _row(claim_id: str) -> dict[str, object]:
    return {
        "article_id": "A-1",
        "sentence_id": claim_id,
        "parent_claim_id": claim_id,
        "claim_id": claim_id,
        "source_sentence": "정부는 물가를 1.8%로 내다봤다.",
        "terminal_status": "HUMAN_REVIEW",
        "reason_code": "CONTEXT_REQUIRED",
        "claim": {"claim_id": claim_id},
        "slot_audit": {"entries": []},
        "stage_results": [],
        "official_resolution": None,
    }


def _after(
    claim_id: str,
    status: str,
    *,
    reclassification_result: str = "",
    next_route: str = "CONTEXT_REVIEW",
) -> dict[str, object]:
    return {
        "claim_id": claim_id,
        "status": status,
        "reason_code": (
            "PRE_VERIFICATION_RECLASSIFIED"
            if status == "RECLASSIFIED"
            else "KOSIS_PIPELINE_ELIGIBLE"
            if status == "PASS"
            else "CONTEXT_REQUIRED"
        ),
        "stop_stage": "CLAIM_PARSE",
        "reclassification_result": reclassification_result,
        "reclassification_reason": "EXPLICIT_FORECAST_OR_POLICY_MARKER",
        "next_route": next_route,
    }


def test_compare_result_preserves_reclassified_as_distinct_outcome() -> None:
    before = build_issue_registry([_row("C-1")])[0]

    compared = compare_result(
        before,
        _after(
            "C-1",
            "RECLASSIFIED",
            reclassification_result="ALL_RECLASSIFIED",
            next_route="PRE_VERIFICATION_EXCLUDE",
        ),
    )

    assert compared.outcome == "RECLASSIFIED"
    assert compared.reclassification_result == "ALL_RECLASSIFIED"
    assert compared.next_route == "PRE_VERIFICATION_EXCLUDE"


def test_child_csv_records_reclassification_and_next_route(tmp_path) -> None:
    path = tmp_path / "children.csv"
    write_context_child_csv(
        [
            {
                "claim_id": "P-1",
                "children": [
                    {
                        "claim_id": "C-1",
                        "admission_route": "STRUCTURAL_HOLD",
                        "twelve_slot_complete": True,
                        "disposition": "FORECAST_OR_POLICY",
                        "disposition_reason": "EXPLICIT_FORECAST_OR_POLICY_MARKER",
                        "next_route": "PRE_VERIFICATION_EXCLUDE",
                        "claim": {},
                        "slot_audit": {"reason_codes": [], "entries": []},
                    }
                ],
            }
        ],
        path,
    )

    with path.open(encoding="utf-8-sig", newline="") as source:
        row = next(csv.DictReader(source))
    assert row["재분류결과"] == "FORECAST_OR_POLICY"
    assert row["재분류사유"] == "EXPLICIT_FORECAST_OR_POLICY_MARKER"
    assert row["다음경로"] == "PRE_VERIFICATION_EXCLUDE"


def test_summary_separates_official_entry_and_reclassification(tmp_path) -> None:
    records = build_issue_registry([_row("C-1"), _row("C-2"), _row("C-3")])
    write_issue_ledgers(records, tmp_path)
    record_group_run(
        records,
        IssueGroup.CONTEXT,
        [
            _after("C-1", "PASS", next_route="OFFICIAL_SEARCH"),
            _after(
                "C-2",
                "RECLASSIFIED",
                reclassification_result="ALL_RECLASSIFIED",
                next_route="PRE_VERIFICATION_EXCLUDE",
            ),
            _after("C-3", "HUMAN_REVIEW"),
        ],
        output_dir=tmp_path,
        run_id="context-reclassified",
        code_version="code-v1",
        data_version="data-v1",
    )

    with (tmp_path / "group_summary.csv").open(
        encoding="utf-8-sig", newline=""
    ) as source:
        row = {item["문제코드"]: item for item in csv.DictReader(source)}["CONTEXT"]
    assert row["공식조회진입수"] == "1"
    assert row["재분류완료수"] == "1"
    assert row["개선수"] == "2"
    assert row["남은수"] == "1"

    with (tmp_path / "runs" / "context-reclassified.csv").open(
        encoding="utf-8-sig", newline=""
    ) as source:
        rows = {item["Claim번호"]: item for item in csv.DictReader(source)}
    assert rows["C-2"]["재분류결과"] == "ALL_RECLASSIFIED"
    assert rows["C-2"]["다음경로"] == "PRE_VERIFICATION_EXCLUDE"
