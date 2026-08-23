from __future__ import annotations

import csv

import pytest

from core.issue_group_harness import IssueGroup, classify_claim
from core.issue_group_harness import build_issue_registry, write_issue_ledgers




@pytest.mark.parametrize(
    ("reason", "expected"),
    [
        ("CONTEXT_REQUIRED", IssueGroup.CONTEXT),
        ("KOSIS_CATALOG_UNAVAILABLE", IssueGroup.OFFICIAL_PATH),
        ("KOSIS_METADATA_UNAVAILABLE", IssueGroup.OFFICIAL_PATH),
        ("NO_HARD_GUARD_CANDIDATE", IssueGroup.HARD_GUARD),
        ("NO_EVIDENCE_COORDINATE_CANDIDATE", IssueGroup.COORDINATE),
        ("LOW_SEMANTIC_SCORE", IssueGroup.SEMANTIC),
        ("AMBIGUOUS_MARGIN", IssueGroup.SEMANTIC),
        ("CONCEPT_NOT_FOUND", IssueGroup.SEMANTIC),
        ("CALCULATION_EVIDENCE_PLAN_UNRESOLVED", IssueGroup.CALCULATION),
        ("CALCULATION_FAILED", IssueGroup.CALCULATION),
        ("FETCH_FAILED", IssueGroup.VALUE_PUBLICATION),
        ("AS_OF_UNAVAILABLE", IssueGroup.VALUE_PUBLICATION),
        ("PUBLICATION_FETCH_FAILED", IssueGroup.VALUE_PUBLICATION),
    ],
)
def test_classify_claim_maps_known_reason_to_one_primary_group(
    reason: str,
    expected: IssueGroup,
) -> None:
    classified = classify_claim(_row(reason=reason))

    assert classified.primary_group is expected
    assert classified.current_reason == reason


def test_classify_claim_routes_auto_to_regression() -> None:
    classified = classify_claim(_row(reason="WITHIN_TOLERANCE", status="AUTO"))

    assert classified.primary_group is IssueGroup.REGRESSION


def test_classify_claim_does_not_guess_unknown_reason() -> None:
    classified = classify_claim(_row(reason="NEW_UNKNOWN_REASON"))

    assert classified.primary_group is IssueGroup.UNCLASSIFIED


def test_classify_claim_uses_earliest_failed_stage_and_keeps_later_failures() -> None:
    row = _row(reason="FETCH_FAILED")
    row["official_resolution"] = {
        "verdict": {
            "route_status": "HOLD",
            "reason_code": "FETCH_FAILED",
            "execution_trace": {
                "events": [
                    {"stage": "SEMANTIC_MAPPING", "status": "PASS", "reason_code": None},
                    {"stage": "HARD_GUARD", "status": "HOLD", "reason_code": "NO_HARD_GUARD_CANDIDATE"},
                    {"stage": "OFFICIAL_VALUE_FETCH", "status": "HOLD", "reason_code": "FETCH_FAILED"},
                ]
            },
        }
    }

    classified = classify_claim(row)

    assert classified.primary_group is IssueGroup.HARD_GUARD
    assert classified.current_stop_stage == "HARD_GUARD"
    assert classified.secondary_issues == ("OFFICIAL_VALUE_FETCH:FETCH_FAILED",)


def test_build_issue_registry_rejects_missing_or_duplicate_claim_identity() -> None:
    missing = _row(reason="CONTEXT_REQUIRED")
    missing["claim_id"] = ""
    with pytest.raises(ValueError, match="MISSING_CLAIM_IDENTITY"):
        build_issue_registry([missing])

    row = _row(reason="CONTEXT_REQUIRED")
    with pytest.raises(ValueError, match="DUPLICATE_CLAIM_IDENTITY"):
        build_issue_registry([row, dict(row)])


def test_write_issue_ledgers_reconciles_master_and_group_rows(tmp_path) -> None:
    rows = [
        _row_with_id("C-001", "CONTEXT_REQUIRED"),
        _row_with_id("C-002", "NO_HARD_GUARD_CANDIDATE"),
        _row_with_id("C-003", "WITHIN_TOLERANCE", status="AUTO"),
    ]
    records = build_issue_registry(rows)

    summary = write_issue_ledgers(records, tmp_path)

    master = tmp_path / "claim_issue_master.csv"
    assert master.read_bytes().startswith(b"\xef\xbb\xbf")
    with master.open(encoding="utf-8-sig", newline="") as source:
        master_rows = list(csv.DictReader(source))
    assert len(master_rows) == 3
    assert {row["Claim번호"] for row in master_rows} == {"C-001", "C-002", "C-003"}
    assert all(row["대표문제"] for row in master_rows)

    group_rows = 0
    for path in (tmp_path / "groups").glob("*.csv"):
        with path.open(encoding="utf-8-sig", newline="") as source:
            group_rows += len(list(csv.DictReader(source)))
    assert group_rows == len(master_rows)
    assert sum(item["전체수"] for item in summary.values()) == len(master_rows)

    with (tmp_path / "group_summary.csv").open(encoding="utf-8-sig", newline="") as source:
        summary_rows = list(csv.DictReader(source))
    assert sum(int(row["전체수"]) for row in summary_rows) == len(master_rows)


def _row(*, reason: str, status: str = "HOLD") -> dict[str, object]:
    return {
        "article_id": "A-001",
        "sentence_id": "S-001",
        "parent_claim_id": "P-001",
        "claim_id": "C-001",
        "source_sentence": "취업자는 10만 명 증가했다.",
        "terminal_status": status,
        "reason_code": reason,
        "claim": {"claim_id": "C-001", "indicator": "취업자"},
        "slot_audit": {"eligible_for_official_search": True, "entries": []},
        "stage_results": [],
        "official_resolution": None,
    }


def _row_with_id(
    claim_id: str,
    reason: str,
    *,
    status: str = "HOLD",
) -> dict[str, object]:
    row = _row(reason=reason, status=status)
    row["claim_id"] = claim_id
    row["parent_claim_id"] = claim_id
    row["claim"] = {"claim_id": claim_id, "indicator": "취업자"}
    return row
