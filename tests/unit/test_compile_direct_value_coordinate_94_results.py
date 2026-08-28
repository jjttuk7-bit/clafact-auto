import csv
import json

from tools.compile_direct_value_coordinate_94_results import compile_artifacts


def _write_csv(path, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def test_compiler_writes_covered_before_after_artifacts(tmp_path) -> None:
    scope = tmp_path / "scope.json"
    specs = tmp_path / "specs.jsonl"
    before = tmp_path / "before.csv"
    classification = tmp_path / "classification.csv"
    live = tmp_path / "live.jsonl"
    coverage = tmp_path / "coverage.json"
    output = tmp_path / "out"
    scope.write_text(json.dumps({"records": [{"claim_id": "C1", "source_sentence": "2025년 취업자는 1명이다."}]}), encoding="utf-8")
    specs.write_text(json.dumps({"claim_id": "C1", "readiness_status": "COORDINATE_READY", "readiness_reasons": [], "indicator": "취업자 수"}) + "\n", encoding="utf-8")
    _write_csv(before, [{"Claim번호": "C1", "최종실패단계": "필수 조건 검사", "최종사유": "NO_HARD_GUARD_CANDIDATE"}])
    _write_csv(classification, [{"Claim번호": "C1", "대표원인": "PERIOD_FREQUENCY_GAP", "적용규칙군": "OFFICIAL_PERIOD_NORMALIZATION"}])
    verdict = {
        "route_status": "AUTO", "verdict": "MATCH", "reason_code": "WITHIN_TOLERANCE",
        "evidence_cells": [{"canonical_key": "K1"}], "evidence_values": [1.0],
        "official_value_provenance": [{"evidence_key": "K1", "source": "API", "source_url": "https://kosis.kr/x", "content_hash": "abc", "retrieved_at": "2026-08-28T00:00:00Z", "publication": {"status": "VERIFIED"}}],
        "execution_trace": {"events": [{"stage": "HARD_GUARD", "status": "PASS"}, {"stage": "OFFICIAL_VALUE_FETCH", "status": "PASS"}, {"stage": "VERDICT", "status": "PASS"}]},
    }
    live.write_text(json.dumps({"claim_id": "C1", "parent_claim_id": "C1", "official_resolution": {"verdict": verdict}}) + "\n", encoding="utf-8")
    coverage.write_text(json.dumps({"input_registry_records": 1, "input_coverage_complete": True, "all_claims_terminal": True, "operational_failure_count": 0, "official_api_counts": {"official_value_fetch_pass": 1}}), encoding="utf-8")

    summary = compile_artifacts(scope, specs, before, classification, live, coverage, output, expected_count=1)

    assert summary["strict_official_complete_count"] == 1
    assert summary["advanced_beyond_original_stage_count"] == 1
    assert (output / "CLAFACT_AUTO_직접값94_공통좌표규칙_전후비교.csv").exists()
    assert (output / "CLAFACT_AUTO_직접값94_공통좌표규칙_결과보고서.txt").exists()
