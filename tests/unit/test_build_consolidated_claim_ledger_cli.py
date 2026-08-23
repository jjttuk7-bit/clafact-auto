import csv
import json
from pathlib import Path

import pytest


def _write_master(path: Path) -> None:
    headers = ["기사번호", "문장번호", "부모Claim번호", "Claim번호", "원문", "대표문제", "현재상태", "현재중단단계", "현재사유", "다음실행단계", "실행횟수"]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        writer.writerow({
            "기사번호": "A1", "문장번호": "1", "부모Claim번호": "C1", "Claim번호": "C1",
            "원문": "원문", "대표문제": "CONTEXT", "현재상태": "HUMAN_REVIEW",
            "현재중단단계": "CLAIM_PARSE", "현재사유": "CONTEXT_REQUIRED",
            "다음실행단계": "CLAIM_PARSE", "실행횟수": "0",
        })


def test_cli_builds_one_row_and_summary(tmp_path: Path) -> None:
    from tools import build_consolidated_claim_ledger as cli

    master = tmp_path / "master.csv"
    _write_master(master)
    results = tmp_path / "results"
    results.mkdir()
    run = results / "run.csv"
    run.write_text(
        "실행번호,Claim번호,개선후상태,개선후단계,개선후사유,개선판정,공식근거확인,기록시각\n"
        "run-1,C1,PASS,CLAIM_PARSE,READY,IMPROVED,아니오,2026-08-23T10:00:00+09:00\n",
        encoding="utf-8-sig",
    )
    output = tmp_path / "CLAFACT_1542_통합진행원장.csv"
    summary = tmp_path / "summary.json"

    assert cli.main([
        str(master), str(output), str(summary),
        "--results-root", str(results), "--expected-count", "1",
    ]) == 0

    with output.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 1
    assert rows[0]["최신결과상태"] == "PASS"
    payload = json.loads(summary.read_text(encoding="utf-8"))
    assert payload["master_count"] == 1
    assert payload["updated_claim_count"] == 1
    assert payload["unmapped_result_count"] == 0


def test_cli_refuses_existing_output_without_replace(tmp_path: Path) -> None:
    from tools import build_consolidated_claim_ledger as cli

    master = tmp_path / "master.csv"
    _write_master(master)
    output = tmp_path / "out.csv"
    summary = tmp_path / "summary.json"
    output.write_text("existing", encoding="utf-8")

    with pytest.raises(SystemExit):
        cli.main([
            str(master), str(output), str(summary),
            "--results-root", str(tmp_path), "--expected-count", "1",
        ])
