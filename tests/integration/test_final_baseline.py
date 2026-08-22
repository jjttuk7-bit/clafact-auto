import json
from pathlib import Path

from core.baseline_registry import build_baseline, validate_baseline, write_baseline
from core.claim_registry_loader import load_claim_registry
from schemas.claim import ClaimSchema
from schemas.claim_registry import ClaimRegistryRecord


def _record(article_id: str, sentence_id: str, sentence: str) -> ClaimRegistryRecord:
    return ClaimRegistryRecord(
        article_id=article_id,
        sentence_id=sentence_id,
        source_ref="test",
        claim=ClaimSchema(
            claim_id="same-claim-id",
            source_sentence=sentence,
            indicator="취업자 수",
            value=10.0,
            unit="만명",
            time="2025-01",
            frequency="M",
            parse_status="AUTO_OK",
        ),
    )


def test_baseline_identity_stays_unique_when_original_claim_ids_repeat() -> None:
    baseline = build_baseline(
        [
            _record("article-1", "1", "첫 번째 기사 주장"),
            _record("article-2", "1", "두 번째 기사 주장"),
        ]
    )

    result = validate_baseline(baseline, expected_count=2)

    assert result.is_valid is True
    assert baseline[0].parent_claim_id != baseline[1].parent_claim_id
    assert [record.source_index for record in baseline] == [1, 2]


def test_write_baseline_preserves_all_records_as_jsonl(tmp_path) -> None:
    baseline = build_baseline([_record("article-1", "1", "첫 주장")])
    output = tmp_path / "01_source_registry.jsonl"

    write_baseline(output, baseline)

    rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 1
    assert rows[0]["article_id"] == "article-1"
    assert rows[0]["source_sentence"] == "첫 주장"


def test_current_registry_builds_complete_1542_record_baseline() -> None:
    path = Path("artifacts/gold_openai_reparse_v1_20260813/claim_registry.jsonl")
    registry = load_claim_registry(path)

    baseline = build_baseline(registry.records)
    result = validate_baseline(baseline, expected_count=1542)

    assert registry.errors == []
    assert result.is_valid is True
    assert result.record_count == 1542
    assert result.unique_parent_count == 1542
    assert result.duplicate_parent_ids == []
    assert result.missing_source_sentence_ids == []

