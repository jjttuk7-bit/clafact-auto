import csv
import json
from datetime import date

import pytest

from schemas.claim import ClaimSchema
from schemas.claim_registry import ClaimRegistryRecord


def _record(claim_id: str, *, change_amount: bool) -> ClaimRegistryRecord:
    if change_amount:
        sentence = "임시근로자는 전년 같은 달보다 1만9000명 감소했다."
        value = 19000
        expression = "1만9000명"
    else:
        sentence = "재배면적은 67만8000ha로 전년보다 감소했다."
        value = 678000
        expression = "67만8000ha"
    claim = ClaimSchema(
        claim_id=claim_id,
        source_sentence=sentence,
        indicator="취업자 수" if change_amount else "재배 면적",
        value=value,
        unit="명" if change_amount else "ha",
        time="2024년 12월" if change_amount else "2024년",
        frequency="월" if change_amount else "년",
        comparison={"type": "YEAR_OVER_YEAR"},
        calculation="DIRECT_VALUE",
        condition={"direction": "DECREASE"},
        parse_status="AUTO_OK",
    )
    return ClaimRegistryRecord(
        article_id=f"article-{claim_id}",
        sentence_id="1",
        article_published_at=date(2025, 1, 15),
        source_ref="test",
        claim=claim,
        slot_enrichment={"target_numeric_expression": expression},
    )


def test_cli_rejects_unbounded_execution(tmp_path) -> None:
    from tools import reclassify_change_amount_group as cli

    with pytest.raises(SystemExit):
        cli.main([
            str(tmp_path / "registry.jsonl"),
            str(tmp_path / "corrected.jsonl"),
            str(tmp_path / "audit.csv"),
        ])


def test_cli_writes_only_source_grounded_reclassified_claims(tmp_path) -> None:
    from tools import reclassify_change_amount_group as cli

    source = tmp_path / "registry.jsonl"
    source.write_text(
        "\n".join([
            _record("change", change_amount=True).model_dump_json(),
            _record("level", change_amount=False).model_dump_json(),
        ]) + "\n",
        encoding="utf-8",
    )
    corrected = tmp_path / "corrected.jsonl"
    audit = tmp_path / "audit.csv"

    assert cli.main([
        str(source), str(corrected), str(audit),
        "--claim-id", "change", "--claim-id", "level",
    ]) == 0

    rows = [json.loads(line) for line in corrected.read_text(encoding="utf-8").splitlines()]
    assert [row["claim"]["claim_id"] for row in rows] == ["change"]
    assert rows[0]["claim"]["calculation"] == "DIFFERENCE"
    assert rows[0]["claim"]["comparison"]["operand_source"] == "OFFICIAL_EVIDENCE"
    assert rows[0]["slot_enrichment"]["change_amount_reclassified"] is True

    with audit.open(encoding="utf-8-sig", newline="") as handle:
        audit_rows = list(csv.DictReader(handle))
    assert [row["claim_id"] for row in audit_rows] == ["change", "level"]
    assert audit_rows[0]["result"] == "RECLASSIFIED"
    assert audit_rows[0]["before_calculation"] == "DIRECT_VALUE"
    assert audit_rows[0]["after_calculation"] == "DIFFERENCE"
    assert audit_rows[1]["result"] == "NOT_RECLASSIFIED"


def _context_target(claim_id: str, article_id: str = "A1") -> ClaimRegistryRecord:
    return ClaimRegistryRecord(
        article_id=article_id,
        sentence_id="11:multi:1",
        article_published_at=date(2025, 6, 11),
        source_ref="test",
        claim=ClaimSchema(
            claim_id=claim_id,
            source_sentence="60세 이상 취업자는 37만명 늘었다.",
            indicator="취업자 수 증가", value=370000, unit="명",
            time="2025년 5월", frequency="월", comparison=None,
            calculation="DIRECT_VALUE", condition={"direction": "INCREASE"},
            parse_status="AUTO_OK",
        ),
        slot_enrichment={"target_numeric_expression": "37만명"},
    )


def _context_sentence(article_id: str, sentence_id: str, sentence: str) -> ClaimRegistryRecord:
    return ClaimRegistryRecord(
        article_id=article_id,
        sentence_id=sentence_id,
        article_published_at=date(2025, 6, 11),
        source_ref="test-context",
        claim=ClaimSchema(
            claim_id=f"context-{article_id}-{sentence_id}",
            source_sentence=sentence,
            parse_status="HOLD",
            parse_reason="CONTEXT_ONLY",
        ),
    )


def test_cli_uses_only_preceding_same_article_context(tmp_path) -> None:
    from tools import reclassify_change_amount_group as cli

    source = tmp_path / "source.jsonl"
    source.write_text(_context_target("target").model_dump_json() + "\n", encoding="utf-8")
    context = tmp_path / "context.jsonl"
    context.write_text("\n".join([
        _context_sentence("A1", "3", "지난달 취업자는 전년 동월 대비 증가했다.").model_dump_json(),
        _context_sentence("A1", "12", "실업자는 전월 대비 감소했다.").model_dump_json(),
        _context_sentence("A2", "2", "취업자는 전월 대비 증가했다.").model_dump_json(),
    ]) + "\n", encoding="utf-8")
    corrected = tmp_path / "corrected.jsonl"
    audit = tmp_path / "audit.csv"

    assert cli.main([
        str(source), str(corrected), str(audit),
        "--context-registry", str(context), "--claim-id", "target",
    ]) == 0

    row = json.loads(corrected.read_text(encoding="utf-8").strip())
    assert row["claim"]["calculation"] == "DIFFERENCE"
    assert row["claim"]["comparison"]["type"] == "YEAR_OVER_YEAR"
    assert row["slot_enrichment"]["comparison_context_sentence_ids"] == ["3"]
    with audit.open(encoding="utf-8-sig", newline="") as handle:
        audit_row = next(csv.DictReader(handle))
    assert audit_row["comparison_context_type"] == "YEAR_OVER_YEAR"
    assert audit_row["comparison_context_sentence_ids"] == "3"


def test_cli_does_not_use_other_article_or_later_context(tmp_path) -> None:
    from tools import reclassify_change_amount_group as cli

    source = tmp_path / "source.jsonl"
    source.write_text(_context_target("target").model_dump_json() + "\n", encoding="utf-8")
    context = tmp_path / "context.jsonl"
    context.write_text("\n".join([
        _context_sentence("A1", "12", "취업자는 전년 동월 대비 증가했다.").model_dump_json(),
        _context_sentence("A2", "2", "취업자는 전년 동월 대비 증가했다.").model_dump_json(),
    ]) + "\n", encoding="utf-8")

    assert cli.main([
        str(source), str(tmp_path / "corrected.jsonl"), str(tmp_path / "audit.csv"),
        "--context-registry", str(context), "--claim-id", "target",
    ]) == 0
    assert (tmp_path / "corrected.jsonl").read_text(encoding="utf-8") == ""
