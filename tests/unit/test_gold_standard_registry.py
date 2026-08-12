from pathlib import Path

from core.gold_standard_registry import validate_gold_standard_registry


def test_gold_standard_registry_validation_reports_count_ids_slots_and_nulls(tmp_path: Path) -> None:
    registry = tmp_path / "claim_registry.jsonl"
    registry.write_text(
        '\n'.join([
            '{"article_id":"A1","sentence_id":"1","article_published_at":"2025-01-01","source_ref":"gold_standard_v1","claim":{"claim_id":"A1_1","source_sentence":"문장 1","indicator":"지표","value":1,"unit":"명","time":"2025-01","frequency":"M","region":null,"population":null,"dimension":null,"comparison":null,"calculation":"DIRECT_VALUE","condition":null,"source_hint":null,"parse_status":"AUTO_OK"}}',
            '{"article_id":"A2","sentence_id":"1","article_published_at":"2025-01-02","source_ref":"gold_standard_v1","claim":{"claim_id":"A2_1","source_sentence":"문장 2","indicator":"다른 지표","value":null,"unit":null,"time":null,"frequency":null,"region":null,"population":null,"dimension":null,"comparison":null,"calculation":null,"condition":null,"source_hint":null,"parse_status":"HOLD"}}',
        ]) + '\n', encoding="utf-8"
    )

    report = validate_gold_standard_registry(registry, expected_count=2)

    assert report["count_matches"] is True
    assert report["claim_id_unique"] is True
    assert report["load_error_count"] == 0
    assert report["slot_non_null_counts"]["indicator"] == 2
    assert report["slot_null_counts"]["region"] == 2


def test_gold_standard_registry_validation_rejects_wrong_source_ref(tmp_path: Path) -> None:
    registry = tmp_path / "claim_registry.jsonl"
    registry.write_text(
        '{"article_id":"A1","sentence_id":"1","source_ref":"other","claim":{"claim_id":"A1_1","source_sentence":"문장","parse_status":"AUTO_OK"}}\n',
        encoding="utf-8",
    )
    report = validate_gold_standard_registry(registry, expected_count=1)
    assert report["source_refs"] == ["other"]
