import json
from pathlib import Path

from core.multi_claim_checkpoint import run_cases_with_checkpoint
from core.multi_claim_group_harness import GoldClaimCase
from core.operational_error import OperationalStageError


def _case(claim_id: str) -> GoldClaimCase:
    return GoldClaimCase(
        article_id=f"article-{claim_id}",
        sentence_id=f"sentence-{claim_id}",
        parent_claim_id=claim_id,
        source_sentence=f"{claim_id} 원문",
        discovered_expressions=("1명",),
        expected_roles={},
        expected_child_count=1,
        expected_route="AUTO",
    )


def test_checkpoint_preserves_progress_and_resume_retries_only_operational_failure(
    tmp_path: Path,
) -> None:
    cases = [_case("c1"), _case("c2"), _case("c3")]
    checkpoint = tmp_path / "checkpoint.jsonl"
    first_calls: list[str] = []

    def first_executor(case: GoldClaimCase) -> dict[str, object]:
        first_calls.append(case.parent_claim_id)
        if case.parent_claim_id == "c2":
            raise OperationalStageError("CLAIM_SPLIT", "diag-c2")
        return {"claim_id": case.parent_claim_id, "status": "PASS", "children": []}

    first = run_cases_with_checkpoint(
        cases,
        first_executor,
        checkpoint,
        signature="signature-v1",
        max_attempts=1,
    )

    assert first_calls == ["c1", "c2", "c3"]
    assert [row["claim_id"] for row in first] == ["c1", "c2", "c3"]
    assert first[1] == {
        "claim_id": "c2",
        "status": "HUMAN_REVIEW",
        "reason_code": "CLAIM_GROUPING_PROVIDER_FAILURE",
        "stop_stage": "CLAIM_SPLIT",
        "executed_stages": ["CLAIM_SPLIT"],
        "children": [],
        "diagnostic_id": "diag-c2",
    }
    persisted = [json.loads(line) for line in checkpoint.read_text(encoding="utf-8").splitlines()]
    assert [row["completed"] for row in persisted] == [True, False, True]

    resumed_calls: list[str] = []

    def resumed_executor(case: GoldClaimCase) -> dict[str, object]:
        resumed_calls.append(case.parent_claim_id)
        return {"claim_id": case.parent_claim_id, "status": "PASS", "children": []}

    resumed = run_cases_with_checkpoint(
        cases,
        resumed_executor,
        checkpoint,
        signature="signature-v1",
        max_attempts=2,
    )

    assert resumed_calls == ["c2"]
    assert all(row["status"] == "PASS" for row in resumed)


def test_checkpoint_signature_change_reprocesses_completed_case(tmp_path: Path) -> None:
    case = _case("c1")
    checkpoint = tmp_path / "checkpoint.jsonl"
    calls: list[str] = []

    def executor(item: GoldClaimCase) -> dict[str, object]:
        calls.append(item.parent_claim_id)
        return {"claim_id": item.parent_claim_id, "status": "PASS", "children": []}

    run_cases_with_checkpoint(
        [case], executor, checkpoint, signature="old", max_attempts=1
    )
    run_cases_with_checkpoint(
        [case], executor, checkpoint, signature="new", max_attempts=1
    )

    assert calls == ["c1", "c1"]
