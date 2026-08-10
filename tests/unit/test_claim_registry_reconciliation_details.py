from core.claim_registry_reconciliation import compare_registry_artifacts


def test_reconciliation_keeps_source_reason_for_each_excluded_record(tmp_path) -> None:
    raw_path = tmp_path / "raw.jsonl"
    structured_path = tmp_path / "structured.jsonl"
    raw_path.write_text(
        '{"article_id":"A2","sentence_id":"3","source_metadata":{"route":"HUMAN_REVIEW","source_type":"UNKNOWN","claim_type":"규모형","reason":"사전 밖"}}\n',
        encoding="utf-8",
    )
    structured_path.write_text("", encoding="utf-8")

    report = compare_registry_artifacts(raw_path, structured_path)

    assert report["raw_only_records"] == [
        {
            "article_id": "A2",
            "sentence_id": "3",
            "route": "HUMAN_REVIEW",
            "source_type": "UNKNOWN",
            "claim_type": "규모형",
            "reason": "사전 밖",
        }
    ]
