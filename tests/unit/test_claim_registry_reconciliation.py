import json

from core.claim_registry_reconciliation import (
    compare_registry_artifacts,
    write_reconciliation_report,
)


def _write_jsonl(path, records) -> None:
    path.write_text(
        "\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n",
        encoding="utf-8",
    )


def test_reconciliation_reports_raw_only_records_and_route_counts(tmp_path) -> None:
    raw_path = tmp_path / "raw.jsonl"
    structured_path = tmp_path / "structured.jsonl"
    _write_jsonl(
        raw_path,
        [
            {"article_id": "A1", "sentence_id": "1", "source_metadata": {"route": "KOSIS_RETRIEVAL"}},
            {"article_id": "A2", "sentence_id": "3", "source_metadata": {"route": "HUMAN_REVIEW"}},
        ],
    )
    _write_jsonl(
        structured_path,
        [{"article_id": "A1", "sentence_id": "1", "source_metadata": {}}],
    )

    report = compare_registry_artifacts(raw_path, structured_path, target_count=2)

    assert report["raw_count"] == 2
    assert report["structured_count"] == 1
    assert report["raw_only_count"] == 1
    assert report["structured_only_count"] == 0
    assert report["target_count_matches"] is False
    assert report["raw_only_route_counts"] == {"HUMAN_REVIEW": 1}
    assert report["raw_only_records"] == [
        {"article_id": "A2", "sentence_id": "3", "route": "HUMAN_REVIEW"}
    ]


def test_reconciliation_report_is_written_as_utf8_json(tmp_path) -> None:
    report_path = write_reconciliation_report({"raw_count": 1600}, tmp_path)

    assert report_path.name == "reconciliation_report.json"
    assert json.loads(report_path.read_text(encoding="utf-8")) == {"raw_count": 1600}
