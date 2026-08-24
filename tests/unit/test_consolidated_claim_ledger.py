import csv
from dataclasses import replace
import json
from pathlib import Path

import pytest

from core.consolidated_claim_ledger import (
    LedgerUpdate,
    build_child_parent_index,
    consolidate_rows,
    discover_updates,
)


def _master(claim_id: str) -> dict[str, str]:
    return {
        "기사번호": "A1",
        "문장번호": "1",
        "부모Claim번호": claim_id,
        "Claim번호": claim_id,
        "원문": "원문",
        "대표문제": "CONTEXT",
        "현재상태": "HUMAN_REVIEW",
        "현재중단단계": "CLAIM_PARSE",
        "현재사유": "CONTEXT_REQUIRED",
        "다음실행단계": "CLAIM_SPLIT~CLAIM_PARSE",
        "실행횟수": "0",
    }


def _update(
    claim_id: str,
    *,
    child: str = "child-1",
    recorded_at: str = "2026-08-23T10:00:00+09:00",
    status: str = "PASS",
    reason: str = "KOSIS_PIPELINE_ELIGIBLE",
    source: str = "runs/context.csv",
) -> LedgerUpdate:
    return LedgerUpdate(
        parent_claim_id=claim_id,
        child_claim_id=child,
        status=status,
        stage="CLAIM_PARSE",
        reason=reason,
        outcome="IMPROVED",
        official_api="아니오",
        table_id="",
        coordinate="",
        official_value="",
        calculated_value="",
        verdict="",
        publication="",
        source_url="",
        source_path=source,
        run_id="context-1",
        recorded_at=recorded_at,
    )


def test_consolidation_preserves_one_row_per_original_claim_and_uses_latest() -> None:
    rows = consolidate_rows([
        _master("C1"), _master("C2"),
    ], [
        _update("C1", recorded_at="2026-08-23T10:00:00+09:00", status="HOLD", reason="STILL_MISSING"),
        _update("C1", recorded_at="2026-08-23T11:00:00+09:00", status="AUTO", reason="WITHIN_TOLERANCE"),
    ])

    assert [row["Claim번호"] for row in rows] == ["C1", "C2"]
    assert rows[0]["최신결과상태"] == "AUTO"
    assert rows[0]["최신결과사유"] == "WITHIN_TOLERANCE"
    assert rows[0]["반영된결과수"] == "2"
    assert rows[1]["최신결과상태"] == ""


def test_consolidation_aggregates_children_without_adding_rows() -> None:
    rows = consolidate_rows([_master("C1")], [
        _update("C1", child="child-1", status="AUTO", reason="WITHIN_TOLERANCE"),
        _update("C1", child="child-2", status="AUTO", reason="OUTSIDE_TOLERANCE"),
    ])

    assert len(rows) == 1
    assert rows[0]["최신자식Claim번호"] == "child-1|child-2"
    assert rows[0]["최신결과상태"] == "AUTO"
    assert rows[0]["최신결과사유"] == "OUTSIDE_TOLERANCE|WITHIN_TOLERANCE"


def test_consolidation_rejects_unknown_claim() -> None:
    with pytest.raises(ValueError, match="RESULT_PARENT_NOT_IN_MASTER:C9"):
        consolidate_rows([_master("C1")], [_update("C9")])


def test_consolidation_rejects_conflicting_same_child_timestamp() -> None:
    with pytest.raises(ValueError, match="CONFLICTING_RESULT"):
        consolidate_rows([_master("C1")], [
            _update("C1", status="AUTO"),
            _update("C1", status="HOLD"),
        ])


def test_child_parent_index_reads_registry_lineage(tmp_path: Path) -> None:
    registry = tmp_path / "reclassified_registry.jsonl"
    registry.write_text(json.dumps({
        "claim": {"claim_id": "child-1"},
        "slot_enrichment": {"parent_claim_id": "C1"},
    }, ensure_ascii=False) + "\n", encoding="utf-8")

    assert build_child_parent_index([tmp_path], {"C1"}) == {"child-1": "C1"}


def _write_csv(path: Path, headers: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def test_discovery_reads_harness_record_official_and_gate_formats(tmp_path: Path) -> None:
    _write_csv(tmp_path / "runs" / "context.csv", [
        "실행번호", "Claim번호", "개선후상태", "개선후단계", "개선후사유",
        "개선판정", "공식근거확인", "공식통계표", "공식값출처", "기록시각",
    ], [{
        "실행번호": "context-1", "Claim번호": "C1", "개선후상태": "PASS",
        "개선후단계": "CLAIM_PARSE", "개선후사유": "READY", "개선판정": "IMPROVED",
        "공식근거확인": "아니오", "공식통계표": "", "공식값출처": "",
        "기록시각": "2026-08-23T10:00:00+09:00",
    }])
    _write_csv(tmp_path / "runs" / "record.csv", [
        "run_id", "parent_claim_id", "child_claim_id", "after_status", "after_reason",
        "official_table", "official_api_verified", "source_urls",
    ], [{
        "run_id": "record-1", "parent_claim_id": "C2", "child_claim_id": "C2:record",
        "after_status": "AUTO", "after_reason": "RECORD_CONFIRMED", "official_table": "T1",
        "official_api_verified": "true", "source_urls": "https://example.test",
    }])
    _write_csv(tmp_path / "official_stage_results.csv", [
        "부모Claim번호", "자식Claim번호", "최종상태", "중단단계", "중단사유",
        "공식API조회여부", "후보통계표", "공식좌표", "공식값", "계산값", "판정",
        "공표확인", "공식값URL", "실행시각",
    ], [{
        "부모Claim번호": "C3", "자식Claim번호": "child-3", "최종상태": "AUTO",
        "중단단계": "VERDICT", "중단사유": "WITHIN_TOLERANCE", "공식API조회여부": "예",
        "후보통계표": "T3", "공식좌표": "T3/2025", "공식값": "10", "계산값": "10",
        "판정": "MATCH", "공표확인": "VERIFIED", "공식값URL": "https://kosis.test",
        "실행시각": "2026-08-23T12:00:00+09:00",
    }])
    _write_csv(tmp_path / "group_completion_gate.csv", [
        "claim_id", "official_values", "calculated_value", "terminal_verdict",
        "terminal_reason", "gate_passed", "official_api_cells", "publication_verified_cells",
    ], [{
        "claim_id": "child-4", "official_values": "10|9", "calculated_value": "1",
        "terminal_verdict": "MATCH", "terminal_reason": "WITHIN_TOLERANCE", "gate_passed": "true",
        "official_api_cells": "2", "publication_verified_cells": "2",
    }])

    updates = discover_updates([tmp_path], {"C1", "C2", "C3", "C4"}, {"child-4": "C4"})

    assert {update.parent_claim_id for update in updates} == {"C1", "C2", "C3", "C4"}
    by_parent = {update.parent_claim_id: update for update in updates}
    assert by_parent["C2"].official_api == "예"
    assert by_parent["C3"].coordinate == "T3/2025"
    assert by_parent["C4"].publication == "2/2"


def test_discovery_reads_multi_claim_parent_result(tmp_path: Path) -> None:
    _write_csv(tmp_path / "multi_claim_result.csv", [
        "부모Claim번호", "자식Claim번호", "분리판정", "재입장결과", "중단사유", "실행시각",
    ], [{
        "부모Claim번호": "C1", "자식Claim번호": "child-1", "분리판정": "일치",
        "재입장결과": "KOSIS_PIPELINE_ELIGIBLE", "중단사유": "",
        "실행시각": "2026-08-23T09:00:00+09:00",
    }])

    update = discover_updates([tmp_path], {"C1"}, {})[0]

    assert update.parent_claim_id == "C1"
    assert update.status == "PASS"
    assert update.stage == "CLAIM_PARSE"


def test_discovery_reads_exact_official_evidence_from_canonical_jsonl(tmp_path: Path) -> None:
    result = tmp_path / "run" / "record-comparison-010.jsonl"
    result.parent.mkdir()
    result.write_text(json.dumps({
        "claim_id": "child-1",
        "parent_claim_id": "child-1",
        "terminal_status": "AUTO",
        "reason_code": "WITHIN_TOLERANCE",
        "lineage_record": {"slot_enrichment": {"parent_claim_id": "C1"}},
        "run_id": "record-comparison-010",
        "stage_results": [{
            "finished_at": "2026-08-23T12:34:56+09:00", "stage": "CLAIM_PARSE",
        }],
        "official_resolution": {"verdict": {
            "verdict": "MATCH",
            "calculated_value": 10,
            "evidence_values": [10, 9],
            "evidence_cells": [
                {"tbl_id": "T_EXACT", "canonical_key": "T_EXACT/2025"},
                {"tbl_id": "T_EXACT", "canonical_key": "T_EXACT/2024"},
            ],
            "official_value_provenance": [
                {"source": "API", "source_url": "https://kosis.test/1", "retrieved_at": "2026-08-23T10:00:00+09:00", "publication": {"status": "VERIFIED"}},
                {"source": "API", "source_url": "https://kosis.test/2", "retrieved_at": "2026-08-23T10:00:00+09:00", "publication": {"status": "VERIFIED"}},
            ],
            "execution_trace": {"events": [{"stage": "VERDICT", "status": "PASS"}]},
        }},
    }, ensure_ascii=False) + "\n", encoding="utf-8")

    update = discover_updates([tmp_path], {"C1"}, {})[0]

    assert update.parent_claim_id == "C1"
    assert update.table_id == "T_EXACT"
    assert update.coordinate == "T_EXACT/2024|T_EXACT/2025"
    assert update.official_api == "예"
    assert update.publication == "2/2"
    assert update.run_id == "record-comparison-010"
    assert update.recorded_at == "2026-08-23T12:34:56+09:00"


def test_latest_event_carries_details_only_from_same_current_children() -> None:
    unrelated = LedgerUpdate(
        parent_claim_id="C1", child_claim_id="old-child", status="AUTO", stage="VERDICT",
        reason="OLD", outcome="RESOLVED", official_api="예", table_id="WRONG_CANDIDATE_LIST",
        coordinate="", official_value="", calculated_value="", verdict="MATCH", publication="",
        source_url="", source_path="old.csv", run_id="old", recorded_at="2026-08-23T09:00:00+09:00",
    )
    exact = LedgerUpdate(
        parent_claim_id="C1", child_claim_id="child-1", status="AUTO", stage="VERDICT",
        reason="WITHIN_TOLERANCE", outcome="RESOLVED", official_api="예", table_id="T_EXACT",
        coordinate="T_EXACT/2025", official_value="10", calculated_value="10", verdict="MATCH",
        publication="1/1", source_url="https://kosis.test", source_path="result.jsonl", run_id="run",
        recorded_at="2026-08-23T10:00:00+09:00",
    )
    exact = replace(exact, source_path="claim_verification_results.jsonl")
    gate = LedgerUpdate(
        parent_claim_id="C1", child_claim_id="child-1", status="AUTO", stage="VERDICT",
        reason="WITHIN_TOLERANCE", outcome="RESOLVED", official_api="예", table_id="",
        coordinate="", official_value="10", calculated_value="10", verdict="MATCH", publication="1/1",
        source_url="", source_path="group_completion_gate.csv", run_id="", recorded_at="2026-08-23T11:00:00+09:00",
    )

    row = consolidate_rows([_master("C1")], [unrelated, exact, gate])[0]

    assert row["최신공식통계표"] == "T_EXACT"
    assert "WRONG_CANDIDATE_LIST" not in row["최신공식통계표"]


def test_latest_failed_event_does_not_inherit_stale_official_values() -> None:
    old = LedgerUpdate(
        parent_claim_id="C1", child_claim_id="child-1", status="AUTO", stage="VERDICT",
        reason="WITHIN_TOLERANCE", outcome="RESOLVED", official_api="예", table_id="T_OLD",
        coordinate="T_OLD/2025", official_value="10", calculated_value="10", verdict="MATCH",
        publication="1/1", source_url="https://old.test", source_path="result.jsonl", run_id="old",
        recorded_at="2026-08-23T10:00:00+09:00",
    )
    failed = LedgerUpdate(
        parent_claim_id="C1", child_claim_id="child-1", status="HOLD", stage="KOSIS_METADATA",
        reason="KOSIS_METADATA_UNAVAILABLE", outcome="UNCHANGED", official_api="아니오", table_id="",
        coordinate="", official_value="", calculated_value="", verdict="UNDETERMINED",
        publication="", source_url="", source_path="failed.jsonl", run_id="new",
        recorded_at="2026-08-23T11:00:00+09:00",
    )

    row = consolidate_rows([_master("C1")], [old, failed])[0]

    assert row["최신결과상태"] == "HOLD"
    assert row["최신공식통계표"] == ""
    assert row["최신공식값"] == ""
    assert row["최신공식값출처"] == ""


@pytest.mark.parametrize("verdict", ["MATCH", "MISMATCH", "RECORD_CONFIRMED", "RECORD_REFUTED"])
def test_terminal_verdicts_are_marked_complete(verdict: str) -> None:
    update = _update("C1", status="AUTO", reason=verdict)
    update = replace(update, verdict=verdict)

    assert consolidate_rows([_master("C1")], [update])[0]["남은작업"] == "완료"


def test_multiple_children_are_complete_when_every_verdict_is_terminal() -> None:
    direct = replace(
        _update("C1", child="direct", status="AUTO"), verdict="MATCH"
    )
    record = replace(
        _update("C1", child="record", status="AUTO"), verdict="RECORD_CONFIRMED"
    )

    row = consolidate_rows([_master("C1")], [direct, record])[0]

    assert row["남은작업"] == "완료"


def test_latest_failure_moves_claim_to_current_issue_group() -> None:
    update = replace(
        _update(
            "C1",
            status="HOLD",
            reason="NO_EVIDENCE_COORDINATE_CANDIDATE",
        ),
        stage="HARD_GUARD",
        verdict="UNDETERMINED",
    )

    row = consolidate_rows([_master("C1")], [update])[0]

    assert row["대표문제"] == "CONTEXT"
    assert row["현재문제묶음"] == "COORDINATE"
    assert row["세부문제유형"] == "COORDINATE_GENERAL"
    assert row["세부문제설명"]
    assert row["해결방법"]
    assert row["처리우선순위"] == "1"
    assert row["대표실행묶음"] == "COORDINATE_GENERAL-001"
