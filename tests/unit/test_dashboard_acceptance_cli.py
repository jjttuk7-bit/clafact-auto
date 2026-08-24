from __future__ import annotations

import csv
import json
from types import SimpleNamespace


def test_cli_runs_completed_rows_and_updates_single_ledger(tmp_path) -> None:
    from tools import run_dashboard_acceptance as cli

    ledger = tmp_path / "ledger.csv"
    with ledger.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "기사번호",
                "문장번호",
                "Claim번호",
                "원문",
                "최신판정",
                "남은작업",
                "현재문제묶음",
            ],
        )
        writer.writeheader()
        writer.writerow({
            "기사번호": "A1",
            "문장번호": "1",
            "Claim번호": "C1",
            "원문": "2025년 고용률은 70%였다.",
            "최신판정": "MATCH",
            "남은작업": "완료",
            "현재문제묶음": "CONTEXT",
        })
    registry = tmp_path / "registry"
    registry.mkdir()
    (registry / "claim_registry.jsonl").write_text(
        json.dumps({
            "article_id": "A1",
            "article_published_at": "2025-01-02",
            "claim": {"claim_id": "C1"},
        }, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    provenance = SimpleNamespace(
        source="API",
        source_url="https://official.example/evidence",
        content_hash="abc123",
        publication=SimpleNamespace(status="VERIFIED"),
    )
    verdict = SimpleNamespace(
        route_status="AUTO",
        verdict="MATCH",
        reason_code="WITHIN_TOLERANCE",
        evidence_cells=[SimpleNamespace(tbl_id="T1", canonical_key="T1/2025")],
        evidence_values=[70.0],
        calculated_value=70.0,
        official_value_provenance=[provenance],
    )
    entry = SimpleNamespace(
        claim=SimpleNamespace(claim_id="child-1", source_sentence="문장"),
        terminal_status="AUTO",
        reason_code=None,
        official_resolution=SimpleNamespace(verdict=verdict),
    )

    class Runtime:
        def verify_article(self, article_text, *, article_published_at):
            assert article_text == "2025년 고용률은 70%였다."
            assert article_published_at.isoformat() == "2025-01-02"
            return SimpleNamespace(entries=[entry])

    output = tmp_path / "run"
    result = cli.main(
        [str(ledger), str(registry), str(output), "--code-version", "abc123"],
        runtime_builder=lambda: Runtime(),
    )

    assert result == 0
    with ledger.open(encoding="utf-8-sig", newline="") as handle:
        updated = list(csv.DictReader(handle))
    assert len(updated) == 1
    assert updated[0]["대시보드검증상태"] == "통과"
    assert updated[0]["대시보드기사작성일"] == "2025-01-02"
    assert updated[0]["대시보드코드버전"] == "abc123"
    assert updated[0]["남은작업"] == "완료"
    with (output / "dashboard_acceptance_results.csv").open(
        encoding="utf-8-sig", newline=""
    ) as handle:
        result_rows = list(csv.DictReader(handle))
    assert len(result_rows) == 1
    assert result_rows[0]["acceptance_status"] == "통과"
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert summary["input_count"] == 1
    assert summary["passed_count"] == 1
    assert summary["failed_count"] == 0
