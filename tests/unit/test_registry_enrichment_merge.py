import json

from core.registry_enrichment_merge import merge_enriched_registry


def test_merge_enriched_registry_writes_complete_derived_input_without_changing_source(tmp_path) -> None:
    source_path = tmp_path / "source.jsonl"
    source_path.write_text(
        "\n".join(
            [
                json.dumps({"article_id": "A1", "sentence_id": "S1", "claim": {"claim_id": "C1"}}),
                json.dumps({"article_id": "A2", "sentence_id": "S2", "claim": {"claim_id": "C2"}}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    enriched_path = tmp_path / "enriched.jsonl"
    enriched_path.write_text(
        json.dumps(
            {
                "article_id": "A1",
                "sentence_id": "S1",
                "claim": {"claim_id": "C1", "calculation": "DIRECT_VALUE"},
                "slot_enrichment": {"status": "ENRICHED"},
            }
        )
        + "\n",
        encoding="utf-8",
    )

    paths = merge_enriched_registry(source_path, enriched_path, tmp_path / "run")

    rows = [json.loads(line) for line in paths.registry_path.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 2
    assert rows[0]["claim"]["calculation"] == "DIRECT_VALUE"
    assert rows[1]["claim"] == {"claim_id": "C2"}
    assert json.loads(paths.report_path.read_text(encoding="utf-8"))["enriched_records_applied"] == 1
    assert "calculation" not in json.loads(source_path.read_text(encoding="utf-8").splitlines()[0])["claim"]
