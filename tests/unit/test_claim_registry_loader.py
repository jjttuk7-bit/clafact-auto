from pathlib import Path

from core.claim_registry_loader import load_claim_registry


def _line(article_id: str = "A1", sentence_id: str = "1") -> str:
    return (
        '{"article_id":"' + article_id + '",'
        '"sentence_id":"' + sentence_id + '",'
        '"source_ref":"test-source",'
        '"claim":{"claim_id":"registry:test:' + article_id + ':' + sentence_id + '",'
        '"source_sentence":"2024년 출생아 수는 24만2334명이었다.",'
        '"parse_status":"AUTO_OK"}}'
    )


def test_loader_returns_typed_valid_records_and_row_errors(tmp_path: Path) -> None:
    path = tmp_path / "registry.jsonl"
    path.write_text(_line() + "\n" + "{invalid json}\n", encoding="utf-8")

    result = load_claim_registry(path)

    assert [record.article_id for record in result.records] == ["A1"]
    assert [(error.line_number, error.reason_code) for error in result.errors] == [
        (2, "INVALID_JSON")
    ]


def test_loader_reports_duplicate_source_key_without_dropping_other_records(tmp_path: Path) -> None:
    path = tmp_path / "registry.jsonl"
    path.write_text(_line() + "\n" + _line() + "\n" + _line("A2", "1") + "\n", encoding="utf-8")

    result = load_claim_registry(path)

    assert [record.article_id for record in result.records] == ["A1", "A2"]
    assert [(error.line_number, error.reason_code) for error in result.errors] == [
        (2, "DUPLICATE_SOURCE_KEY")
    ]


def test_loader_reports_invalid_claim_schema(tmp_path: Path) -> None:
    path = tmp_path / "registry.jsonl"
    path.write_text(
        _line().replace('"parse_status":"AUTO_OK"', '"parse_status":"INVALID"') + "\n",
        encoding="utf-8",
    )

    result = load_claim_registry(path)

    assert result.records == []
    assert [(error.line_number, error.reason_code) for error in result.errors] == [
        (1, "INVALID_REGISTRY_RECORD")
    ]
