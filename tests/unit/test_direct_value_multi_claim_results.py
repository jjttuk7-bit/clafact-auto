from hashlib import sha256
import json
from pathlib import Path

import pytest

from core.direct_value_multi_claim_results import (
    compile_multi_claim_results,
    write_multi_claim_deliverables,
)
from core.direct_value_multi_claim_scope import (
    DirectValueMultiClaimCase,
    DirectValueMultiClaimScope,
)
from schemas.claim_registry import ClaimRegistryRecord


def _case(claim_id: str, sentence: str, expressions: tuple[str, ...]):
    return DirectValueMultiClaimCase(
        parent_claim_id=claim_id,
        source_sentence=sentence,
        expressions=expressions,
        source_row={
            "Claim번호": claim_id,
            "기사번호": "A1",
            "문장번호": claim_id,
            "기사작성일": "2025-01-15",
            "원문": sentence,
            "숫자역할안전판정": "SAFE_TARGET_ROLE",
        },
    )


def _child(parent_id: str, child_id: str, value: float) -> dict:
    sentence = "실업률은 4%이고 취업자는 25만명 늘었다."
    return {
        "parent_claim_id": parent_id,
        "child_claim_id": child_id,
        "recovery_action": "MULTI_CLAIM_SPLIT",
        "admission_route": "KOSIS_PIPELINE_ELIGIBLE",
        "terminal_status": "AUTO",
        "reason_code": "WITHIN_TOLERANCE",
        "diagnostic_id": None,
        "claim": {
            "claim_id": child_id,
            "source_sentence": sentence,
            "indicator": "실업률",
            "value": value,
            "unit": "%",
            "time": "2024-12",
            "frequency": "월",
            "region": None,
            "population": None,
            "dimension": None,
            "comparison": None,
            "calculation": "DIRECT_VALUE",
            "condition": None,
            "source_hint": None,
            "parse_status": "AUTO_OK",
            "parse_reason": None,
        },
        "official_resolution": {
            "verdict": {
                "verdict": "MATCH",
                "route_status": "AUTO",
                "reason_code": "WITHIN_TOLERANCE",
                "evidence_cells": [{"canonical_key": "KOSIS:1", "status": "CONFIRMED"}],
                "official_value_provenance": [{
                    "source": "API",
                    "evidence_key": "KOSIS:1",
                    "source_url": "https://kosis.kr/openapi/example",
                    "content_hash": "abc123",
                    "retrieved_at": "2026-08-26T00:00:00Z",
                    "publication": {"status": "VERIFIED"},
                }],
            }
        },
        "lineage_record": {
            "parent_claim_id": parent_id,
            "child_claim_id": child_id,
            "child_ordinal": 1,
            "source_sentence": sentence,
            "target_expression": "4%",
        },
        "stage_results": [],
        "slot_audit": {"eligible_for_official_search": True, "entries": [], "reason_codes": []},
    }


def _write_checkpoint(path: Path, rows: list[dict], signature: str) -> None:
    path.write_text(
        "".join(
            json.dumps({
                "parent_claim_id": row["parent_claim_id"],
                "signature": signature,
                "completed": True,
                "result": row,
            }, ensure_ascii=False) + "\n"
            for row in rows
        ),
        encoding="utf-8",
    )


def _source_hash(sentence: str) -> str:
    return sha256(sentence.encode("utf-8")).hexdigest().upper()


def test_compile_uses_retry_result_and_preserves_single_parent(tmp_path: Path) -> None:
    single = _case("C1", "취업자는 2800만명이다.", ("2800만명",))
    grouped = _case(
        "C2",
        "실업률은 4%이고 취업자는 25만명 늘었다.",
        ("4%", "25만명"),
    )
    scope = DirectValueMultiClaimScope(
        parents=(single, grouped),
        single_cases=(single,),
        grouping_cases=(grouped,),
        source_sha256="SOURCE",
    )
    primary = tmp_path / "primary.jsonl"
    retry = tmp_path / "retry.jsonl"
    _write_checkpoint(primary, [{
        "parent_claim_id": "C2",
        "source_sentence_sha256": _source_hash(grouped.source_sentence),
        "expressions": ["4%", "25만명"],
        "status": "HUMAN_REVIEW",
        "reason_code": "KOSIS_CATALOG_UNAVAILABLE",
        "children": [{**_child("C2", "failed", 4.0), "terminal_status": "HUMAN_REVIEW", "reason_code": "KOSIS_CATALOG_UNAVAILABLE"}],
    }], "PRIMARY")
    _write_checkpoint(retry, [{
        "parent_claim_id": "C2",
        "source_sentence_sha256": _source_hash(grouped.source_sentence),
        "expressions": ["4%", "25만명"],
        "status": "PASS",
        "reason_code": None,
        "children": [_child("C2", "child-1", 4.0), _child("C2", "child-2", 250000.0)],
    }], "RETRY")

    compiled = compile_multi_claim_results(scope, primary, retry)

    assert len(compiled.parent_rows) == 2
    assert compiled.parent_rows[0]["복수Claim처리구분"] == "단일통계값_분리불필요"
    assert compiled.parent_rows[1]["재시도적용"] == "Y"
    assert compiled.parent_rows[1]["부모실행상태"] == "PASS"
    assert len(compiled.child_rows) == 2
    assert compiled.report["재시도회복부모수"] == 1
    assert compiled.report["유효자식Claim수"] == 2
    assert all(ClaimRegistryRecord.model_validate(row) for row in compiled.registry_rows)


def test_compile_rejects_missing_grouping_parent(tmp_path: Path) -> None:
    grouped = _case("C2", "실업률은 4%이고 취업자는 25만명 늘었다.", ("4%", "25만명"))
    scope = DirectValueMultiClaimScope(
        parents=(grouped,),
        single_cases=(),
        grouping_cases=(grouped,),
        source_sha256="SOURCE",
    )
    checkpoint = tmp_path / "empty.jsonl"
    checkpoint.write_text("", encoding="utf-8")

    with pytest.raises(ValueError, match="MULTI_CLAIM_RESULT_COVERAGE_MISMATCH"):
        compile_multi_claim_results(scope, checkpoint)


def test_write_deliverables_creates_auditable_files(tmp_path: Path) -> None:
    single = _case("C1", "취업자는 2800만명이다.", ("2800만명",))
    grouped = _case("C2", "실업률은 4%이고 취업자는 25만명 늘었다.", ("4%", "25만명"))
    scope = DirectValueMultiClaimScope(
        parents=(single, grouped),
        single_cases=(single,),
        grouping_cases=(grouped,),
        source_sha256="SOURCE",
    )
    checkpoint = tmp_path / "primary.jsonl"
    _write_checkpoint(checkpoint, [{
        "parent_claim_id": "C2",
        "source_sentence_sha256": _source_hash(grouped.source_sentence),
        "expressions": ["4%", "25만명"],
        "status": "PASS",
        "reason_code": None,
        "children": [_child("C2", "child-1", 4.0)],
    }], "PRIMARY")
    compiled = compile_multi_claim_results(scope, checkpoint)

    outputs = write_multi_claim_deliverables(compiled, tmp_path, date_tag="20260826")

    assert len(outputs) == 8
    assert all(path.exists() for path in outputs.values())
    assert outputs["parents_csv"].read_bytes().startswith(b"\xef\xbb\xbf")
    checklist = json.loads(outputs["checklist_json"].read_text(encoding="utf-8"))
    assert checklist["phase_1_task_7"]["checked"] is True


def test_auto_without_official_evidence_is_not_counted_as_official_complete(tmp_path: Path) -> None:
    grouped = _case("C2", "실업률은 4%이고 취업자는 25만명 늘었다.", ("4%", "25만명"))
    scope = DirectValueMultiClaimScope((grouped,), (), (grouped,), "SOURCE")
    child = _child("C2", "child-1", 4.0)
    child["official_resolution"] = {"verdict": {"verdict": "MATCH", "route_status": "AUTO"}}
    checkpoint = tmp_path / "primary.jsonl"
    _write_checkpoint(checkpoint, [{
        "parent_claim_id": "C2",
        "source_sentence_sha256": _source_hash(grouped.source_sentence),
        "expressions": ["4%", "25만명"],
        "status": "PASS",
        "reason_code": None,
        "children": [child],
    }], "PRIMARY")
    compiled = compile_multi_claim_results(scope, checkpoint)
    assert compiled.report["자동경로도달자식수"] == 1
    assert compiled.report["공식판정완료자식수"] == 0


def test_grouping_ambiguous_child_keeps_parent_in_review(tmp_path: Path) -> None:
    grouped = _case("C2", "실업률은 4%이고 취업자는 25만명 늘었다.", ("4%", "25만명"))
    scope = DirectValueMultiClaimScope((grouped,), (), (grouped,), "SOURCE")
    child = _child("C2", "child-1", 4.0)
    child.update(terminal_status="HUMAN_REVIEW", reason_code="GROUPING_AMBIGUOUS")
    checkpoint = tmp_path / "primary.jsonl"
    _write_checkpoint(checkpoint, [{
        "parent_claim_id": "C2",
        "source_sentence_sha256": _source_hash(grouped.source_sentence),
        "expressions": ["4%", "25만명"],
        "status": "PASS",
        "reason_code": None,
        "children": [child],
    }], "PRIMARY")
    compiled = compile_multi_claim_results(scope, checkpoint)
    assert compiled.parent_rows[0]["부모실행상태"] == "HUMAN_REVIEW"
    assert compiled.parent_rows[0]["부모실행사유"] == "GROUPING_AMBIGUOUS"
    assert compiled.report["최종분리확정부모수"] == 0
    assert compiled.report["최종검토필요부모수"] == 1


def test_rejects_checkpoint_from_different_source_sentence(tmp_path: Path) -> None:
    grouped = _case("C2", "실업률은 4%이고 취업자는 25만명 늘었다.", ("4%", "25만명"))
    scope = DirectValueMultiClaimScope((grouped,), (), (grouped,), "SOURCE")
    checkpoint = tmp_path / "primary.jsonl"
    _write_checkpoint(checkpoint, [{
        "parent_claim_id": "C2",
        "source_sentence_sha256": _source_hash("다른 원문"),
        "expressions": ["4%", "25만명"],
        "status": "PASS",
        "reason_code": None,
        "children": [_child("C2", "child-1", 4.0)],
    }], "PRIMARY")
    with pytest.raises(ValueError, match="MULTI_CLAIM_CHECKPOINT_SOURCE_MISMATCH"):
        compile_multi_claim_results(scope, checkpoint)


def test_rejects_retry_for_non_operational_primary_result(tmp_path: Path) -> None:
    grouped = _case("C2", "실업률은 4%이고 취업자는 25만명 늘었다.", ("4%", "25만명"))
    scope = DirectValueMultiClaimScope((grouped,), (), (grouped,), "SOURCE")
    primary = tmp_path / "primary.jsonl"
    retry = tmp_path / "retry.jsonl"
    base = {
        "parent_claim_id": "C2",
        "source_sentence_sha256": _source_hash(grouped.source_sentence),
        "expressions": ["4%", "25만명"],
        "status": "PASS",
        "reason_code": None,
        "children": [_child("C2", "child-1", 4.0)],
    }
    _write_checkpoint(primary, [base], "PRIMARY")
    _write_checkpoint(retry, [base], "RETRY")
    with pytest.raises(ValueError, match="MULTI_CLAIM_RETRY_NOT_OPERATIONAL_FAILURE"):
        compile_multi_claim_results(scope, primary, retry)


def test_official_complete_requires_one_provenance_per_evidence_key(tmp_path: Path) -> None:
    grouped = _case("C2", "실업률은 4%이고 취업자는 25만명 늘었다.", ("4%", "25만명"))
    scope = DirectValueMultiClaimScope((grouped,), (), (grouped,), "SOURCE")
    child = _child("C2", "child-1", 4.0)
    verdict = child["official_resolution"]["verdict"]
    verdict["evidence_cells"] = [
        {"canonical_key": "KOSIS:A", "status": "CONFIRMED"},
        {"canonical_key": "KOSIS:B", "status": "CONFIRMED"},
    ]
    provenance = dict(verdict["official_value_provenance"][0])
    provenance["evidence_key"] = "KOSIS:A"
    verdict["official_value_provenance"] = [provenance, dict(provenance)]
    checkpoint = tmp_path / "primary.jsonl"
    _write_checkpoint(checkpoint, [{
        "parent_claim_id": "C2",
        "source_sentence_sha256": _source_hash(grouped.source_sentence),
        "expressions": ["4%", "25만명"],
        "status": "PASS",
        "reason_code": None,
        "children": [child],
    }], "PRIMARY")

    compiled = compile_multi_claim_results(scope, checkpoint)

    assert compiled.report["공식판정완료자식수"] == 0
