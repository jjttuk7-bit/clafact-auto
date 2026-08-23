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
