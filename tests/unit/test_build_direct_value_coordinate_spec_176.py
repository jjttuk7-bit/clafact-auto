import csv
import json
from pathlib import Path

from tools.build_direct_value_coordinate_spec_176 import build_artifacts


def test_build_artifacts_writes_complete_auditable_bundle(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.csv"
    rows = [{
        "원본부모Claim번호": "C1", "자식Claim번호": "C1", "기사그룹ID": "A1",
        "원문": "2024년 전국 출생아 수는 1명이다.", "기사작성일": "2025-01-10",
        "지표": "출생아 수", "기사값": "1", "단위": "명", "기준시점": "2024",
        "주기": "Y", "지역": "전국", "계산방식": "DIRECT_VALUE", "파싱상태": "AUTO_OK",
        "대상수치표현": "1명", "복구48최종사유": "NO_HARD_GUARD_CANDIDATE",
    }]
    with ledger.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    manifest = build_artifacts(ledger, tmp_path / "out", expected_count=1)

    assert manifest["scope_count"] == 1
    assert manifest["query_spec_count"] == 1
    assert manifest["ready_count"] == 1
    assert (tmp_path / "out" / "query_specs.jsonl").exists()
    assert (tmp_path / "out" / "ready_registry.jsonl").exists()
    saved = json.loads((tmp_path / "out" / "manifest.json").read_text(encoding="utf-8"))
    assert saved["input_ledger_sha256"] == manifest["input_ledger_sha256"]
