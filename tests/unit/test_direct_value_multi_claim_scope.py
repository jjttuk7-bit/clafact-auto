import csv
from pathlib import Path

import pytest

from core.direct_value_multi_claim_scope import (
    load_direct_value_multi_claim_scope,
    run_scope_with_checkpoint,
)


def write_source(path: Path) -> None:
    rows = [
        {
            "Claim번호": "C1",
            "원문": "취업자 수는 2800만명이다.",
            "숫자역할안전판정": "SAFE_TARGET_ROLE",
        },
        {
            "Claim번호": "C2",
            "원문": "실업률은 4%이고 일자리는 25만개 늘었다.",
            "숫자역할안전판정": "SAFE_TARGET_ROLE",
        },
        {
            "Claim번호": "C3",
            "원문": "소비자물가 지수는 116.38로 전년보다 2.1% 올랐다.",
            "숫자역할안전판정": "SAFE_TARGET_ROLE",
        },
        {
            "Claim번호": "BLOCKED",
            "원문": "20대 인구는 700만명이다.",
            "숫자역할안전판정": "PROTECTED_CONTEXT_BLOCKED",
        },
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def test_loads_only_safe_parents_and_separates_external_candidates(tmp_path: Path) -> None:
    source = tmp_path / "source.csv"
    write_source(source)

    scope = load_direct_value_multi_claim_scope(
        source,
        expected_parent_count=3,
        approved_external_limit=2,
    )

    assert [case.parent_claim_id for case in scope.parents] == ["C1", "C2", "C3"]
    assert [case.parent_claim_id for case in scope.single_cases] == ["C1"]
    assert [case.parent_claim_id for case in scope.grouping_cases] == ["C2", "C3"]
    assert scope.grouping_cases[1].expressions == ("116.38", "2.1%")


def test_stops_before_external_execution_when_approval_limit_is_exceeded(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.csv"
    write_source(source)

    with pytest.raises(ValueError, match="APPROVED_EXTERNAL_SCOPE_EXCEEDED:2:1"):
        load_direct_value_multi_claim_scope(
            source,
            expected_parent_count=3,
            approved_external_limit=1,
        )


def test_checkpoint_resumes_same_signature_and_reexecutes_new_signature(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.csv"
    write_source(source)
    scope = load_direct_value_multi_claim_scope(
        source,
        expected_parent_count=3,
        approved_external_limit=2,
    )
    checkpoint = tmp_path / "checkpoint.jsonl"
    calls: list[str] = []

    def execute(case):
        calls.append(case.parent_claim_id)
        return {"parent_claim_id": case.parent_claim_id, "status": "PASS"}

    first = run_scope_with_checkpoint(
        scope.grouping_cases,
        execute,
        checkpoint,
        signature="sig-1",
        start=0,
        limit=20,
    )
    second = run_scope_with_checkpoint(
        scope.grouping_cases,
        execute,
        checkpoint,
        signature="sig-1",
        start=0,
        limit=20,
    )
    third = run_scope_with_checkpoint(
        scope.grouping_cases,
        execute,
        checkpoint,
        signature="sig-2",
        start=0,
        limit=20,
    )

    assert [row["parent_claim_id"] for row in first] == ["C2", "C3"]
    assert second == first
    assert third == first
    assert calls == ["C2", "C3", "C2", "C3"]
