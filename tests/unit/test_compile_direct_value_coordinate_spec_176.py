import json
from pathlib import Path

from tools.compile_direct_value_coordinate_spec_176 import compile_artifacts


def test_compile_artifacts_writes_csv_summary_and_korean_report(tmp_path: Path) -> None:
    scope = {"records": [{
        "claim_id": "C1", "source_sentence": "값은 1명이다.",
        "current_reason": "OLD", "split_set": "RULE_DISCOVERY",
    }]}
    (tmp_path / "scope.json").write_text(json.dumps(scope, ensure_ascii=False), encoding="utf-8")
    (tmp_path / "query_specs.jsonl").write_text(json.dumps({
        "claim_id": "C1", "indicator": "출생아 수", "value": 1, "unit": "명",
        "readiness_status": "PRE_VERIFICATION", "readiness_reasons": ["MISSING_TIME"],
    }, ensure_ascii=False) + "\n", encoding="utf-8")
    live = tmp_path / "live.jsonl"
    live.write_text("", encoding="utf-8")

    summary = compile_artifacts(
        tmp_path / "scope.json", tmp_path / "query_specs.jsonl", live, tmp_path / "out"
    )

    assert summary["scope_count"] == 1
    assert (tmp_path / "out" / "CLAFACT_AUTO_직접값176_단계별평가표.csv").exists()
    report = (tmp_path / "out" / "CLAFACT_AUTO_직접값176_결과보고서.txt").read_text(encoding="utf-8")
    assert "전체 176건" in report
    assert "단계별" in report
