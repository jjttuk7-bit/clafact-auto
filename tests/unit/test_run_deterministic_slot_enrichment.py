import json
from pathlib import Path

from tools.run_deterministic_slot_enrichment import run


def test_run_writes_enriched_jsonl_and_coverage_report_under_output_dir(tmp_path: Path) -> None:
    source_path = tmp_path / "registry.jsonl"
    source_path.write_text(
        json.dumps(
            {
                "article_id": "A1",
                "sentence_id": "1",
                "claim": {
                    "claim_id": "registry:test:A1:1",
                    "source_sentence": "수출은 전년 동월 대비 3% 증가했다.",
                    "parse_status": "AUTO_OK",
                },
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    output_dir = tmp_path / "output"

    records_path, report_path = run(source_path, output_dir)

    assert records_path == output_dir / "deterministic_enriched_claims.jsonl"
    assert report_path == output_dir / "coverage_report.json"
    assert json.loads(records_path.read_text(encoding="utf-8")) ["claim"]["calculation"] == "GROWTH_RATE"
    assert json.loads(report_path.read_text(encoding="utf-8"))["total_records"] == 1
