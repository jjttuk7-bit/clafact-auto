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
from core.issue_group_harness import run_group_slice, select_group_slice


def test_select_group_slice_requires_one_group_and_limit_between_one_and_fifty() -> None:
    records = build_issue_registry(
        [
            _row_with_id("C-002", "CONTEXT_REQUIRED"),
            _row_with_id("C-001", "CONTEXT_REQUIRED"),
        ]
    )

    with pytest.raises(ValueError, match="GROUP_REQUIRED"):
        select_group_slice(records, None, limit=20)
    with pytest.raises(ValueError, match="UNCLASSIFIED_GROUP_CANNOT_RUN"):
        select_group_slice(records, IssueGroup.UNCLASSIFIED, limit=20)
    with pytest.raises(ValueError, match="LIMIT_MUST_BE_BETWEEN_1_AND_50"):
        select_group_slice(records, IssueGroup.CONTEXT, limit=0)
    with pytest.raises(ValueError, match="LIMIT_MUST_BE_BETWEEN_1_AND_50"):
        select_group_slice(records, IssueGroup.CONTEXT, limit=51)

    selected = select_group_slice(records, IssueGroup.CONTEXT, limit=1)
    assert [record.claim_id for record in selected] == ["C-001"]


def test_run_group_slice_exposes_only_the_selected_groups_allowed_stages() -> None:
    records = build_issue_registry([_row_with_id("C-001", "CONTEXT_REQUIRED")])
    observed: list[tuple[str, ...]] = []

    def executor(record, allowed_stages):
        observed.append(allowed_stages)
        return {"claim_id": record.claim_id, "executed_stages": list(allowed_stages)}

    results = run_group_slice(records, IssueGroup.CONTEXT, executor, limit=1)

    assert observed == [("CLAIM_SPLIT", "CLAIM_PARSE")]
    assert results[0]["executed_stages"] == ["CLAIM_SPLIT", "CLAIM_PARSE"]


def test_run_group_slice_rejects_a_downstream_stage_reported_by_executor() -> None:
    records = build_issue_registry([_row_with_id("C-001", "CONTEXT_REQUIRED")])

    def executor(record, allowed_stages):
        return {
            "claim_id": record.claim_id,
            "executed_stages": [*allowed_stages, "CATALOG_SEARCH"],
        }

    with pytest.raises(ValueError, match="STAGE_OUT_OF_GROUP_POLICY:CATALOG_SEARCH"):
        run_group_slice(records, IssueGroup.CONTEXT, executor, limit=1)


from core.issue_group_harness import evaluate_group_gate, record_group_run


def test_record_group_run_writes_before_after_csv_and_updates_master(tmp_path) -> None:
    records = build_issue_registry(
        [
            _row_with_id("C-001", "NO_HARD_GUARD_CANDIDATE"),
            _row_with_id("C-002", "NO_HARD_GUARD_CANDIDATE"),
            _row_with_id("C-003", "NO_HARD_GUARD_CANDIDATE"),
        ]
    )
    write_issue_ledgers(records, tmp_path)

    comparisons = record_group_run(
        records,
        IssueGroup.HARD_GUARD,
        [
            {
                "claim_id": "C-001",
                "status": "HOLD",
                "reason_code": "NO_EVIDENCE_COORDINATE_CANDIDATE",
                "stop_stage": "EVIDENCE_CELL",
            },
            {
                "claim_id": "C-002",
                "status": "HOLD",
                "reason_code": "NO_HARD_GUARD_CANDIDATE",
                "stop_stage": "HARD_GUARD",
            },
            {
                "claim_id": "C-003",
                "status": "HOLD",
                "reason_code": "CONCEPT_NOT_FOUND",
                "stop_stage": "SEMANTIC_MAPPING",
            },
        ],
        output_dir=tmp_path,
        run_id="hard-guard-001",
        code_version="code-v1",
        data_version="data-v1",
    )

    assert [item.outcome for item in comparisons] == [
        "IMPROVED",
        "UNCHANGED",
        "REGRESSED",
    ]
    with (tmp_path / "runs" / "hard-guard-001.csv").open(
        encoding="utf-8-sig", newline=""
    ) as source:
        run_rows = list(csv.DictReader(source))
    assert len(run_rows) == 3
    assert run_rows[0]["개선판정"] == "IMPROVED"

    with (tmp_path / "claim_issue_master.csv").open(
        encoding="utf-8-sig", newline=""
    ) as source:
        master = {row["Claim번호"]: row for row in csv.DictReader(source)}
    assert master["C-001"]["개선후사유"] == "NO_EVIDENCE_COORDINATE_CANDIDATE"
    assert master["C-001"]["실행횟수"] == "1"


def test_group_gate_rejects_unchanged_regressed_or_missing_official_evidence(tmp_path) -> None:
    records = build_issue_registry(
        [
            _row_with_id("C-001", "FETCH_FAILED"),
            _row_with_id("C-002", "FETCH_FAILED"),
        ]
    )
    comparisons = record_group_run(
        records,
        IssueGroup.VALUE_PUBLICATION,
        [
            {
                "claim_id": "C-001",
                "status": "AUTO",
                "reason_code": "WITHIN_TOLERANCE",
                "stop_stage": "VERDICT",
                "official_evidence": True,
            },
            {
                "claim_id": "C-002",
                "status": "AUTO",
                "reason_code": "WITHIN_TOLERANCE",
                "stop_stage": "VERDICT",
                "official_evidence": False,
            },
        ],
        output_dir=tmp_path,
        run_id="value-001",
        code_version="code-v1",
        data_version="data-v1",
    )

    gate = evaluate_group_gate(
        IssueGroup.VALUE_PUBLICATION,
        comparisons,
        expected_claim_ids={"C-001", "C-002"},
        gate_dir=tmp_path / "gates",
        code_version="code-v1",
        data_version="data-v1",
    )

    assert gate.passed is False
    assert "MISSING_OFFICIAL_EVIDENCE:C-002" in gate.reasons


def test_group_gate_passes_and_persists_version_bound_completion(tmp_path) -> None:
    records = build_issue_registry([_row_with_id("C-001", "CONTEXT_REQUIRED")])
    comparisons = record_group_run(
        records,
        IssueGroup.CONTEXT,
        [{"claim_id": "C-001", "status": "AUTO", "stop_stage": "VERDICT"}],
        output_dir=tmp_path,
        run_id="context-001",
        code_version="code-v1",
        data_version="data-v1",
    )

    gate = evaluate_group_gate(
        IssueGroup.CONTEXT,
        comparisons,
        expected_claim_ids={"C-001"},
        gate_dir=tmp_path / "gates",
        code_version="code-v1",
        data_version="data-v1",
    )

    assert gate.passed is True
    assert (tmp_path / "gates" / "CONTEXT.json").is_file()


import json
from core.issue_group_harness import authorize_final_full_run


def test_final_full_run_is_denied_without_explicit_authorization_and_all_gates(tmp_path) -> None:
    records = build_issue_registry(
        [
            _row_with_id("C-001", "CONTEXT_REQUIRED"),
            _row_with_id("C-002", "NO_HARD_GUARD_CANDIDATE"),
        ]
    )
    _write_gate(tmp_path, IssueGroup.CONTEXT, passed=True)

    result = authorize_final_full_run(
        records,
        gate_dir=tmp_path,
        code_version="code-v1",
        data_version="data-v1",
        explicit_authorization=False,
    )

    assert result.authorized is False
    assert "EXPLICIT_FINAL_AUTHORIZATION_REQUIRED" in result.reasons
    assert "MISSING_GROUP_GATE:HARD_GUARD" in result.reasons


def test_final_full_run_is_denied_for_failed_or_stale_gate(tmp_path) -> None:
    records = build_issue_registry(
        [
            _row_with_id("C-001", "CONTEXT_REQUIRED"),
            _row_with_id("C-002", "NO_HARD_GUARD_CANDIDATE"),
        ]
    )
    _write_gate(tmp_path, IssueGroup.CONTEXT, passed=False)
    _write_gate(
        tmp_path,
        IssueGroup.HARD_GUARD,
        passed=True,
        code_version="old-code",
    )

    result = authorize_final_full_run(
        records,
        gate_dir=tmp_path,
        code_version="code-v1",
        data_version="data-v1",
        explicit_authorization=True,
    )

    assert "FAILED_GROUP_GATE:CONTEXT" in result.reasons
    assert "STALE_GROUP_GATE:HARD_GUARD" in result.reasons


def test_final_full_run_is_denied_while_unclassified_claims_remain(tmp_path) -> None:
    records = build_issue_registry([_row_with_id("C-001", "UNKNOWN_NEW_REASON")])

    result = authorize_final_full_run(
        records,
        gate_dir=tmp_path,
        code_version="code-v1",
        data_version="data-v1",
        explicit_authorization=True,
    )

    assert result.authorized is False
    assert result.reasons == ("UNCLASSIFIED_CLAIMS_REMAIN:1",)


def test_final_full_run_is_authorized_only_when_every_required_gate_is_current(tmp_path) -> None:
    records = build_issue_registry(
        [
            _row_with_id("C-001", "CONTEXT_REQUIRED"),
            _row_with_id("C-002", "NO_HARD_GUARD_CANDIDATE"),
            _row_with_id("C-003", "WITHIN_TOLERANCE", status="AUTO"),
        ]
    )
    _write_gate(tmp_path, IssueGroup.CONTEXT, passed=True)
    _write_gate(tmp_path, IssueGroup.HARD_GUARD, passed=True)

    result = authorize_final_full_run(
        records,
        gate_dir=tmp_path,
        code_version="code-v1",
        data_version="data-v1",
        explicit_authorization=True,
    )

    assert result.authorized is True
    assert result.reasons == ()


def _write_gate(
    gate_dir,
    group: IssueGroup,
    *,
    passed: bool,
    code_version: str = "code-v1",
    data_version: str = "data-v1",
) -> None:
    gate_dir.mkdir(parents=True, exist_ok=True)
    (gate_dir / f"{group.value}.json").write_text(
        json.dumps(
            {
                "group": group.value,
                "passed": passed,
                "code_version": code_version,
                "data_version": data_version,
            }
        ),
        encoding="utf-8",
    )
