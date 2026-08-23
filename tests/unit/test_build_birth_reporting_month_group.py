import csv
from datetime import date
import json
from pathlib import Path

from schemas.claim import ClaimSchema
from schemas.claim_registry import ClaimRegistryRecord


def _record(claim_id: str, sentence_id: str, source: str, *, calculation: str = "GROWTH_RATE") -> ClaimRegistryRecord:
    return ClaimRegistryRecord(
        article_id="A1",
        sentence_id=sentence_id,
        article_published_at=date(2025, 6, 26),
        source_ref="test",
        source_metadata={"domain": "population_household"},
        claim=ClaimSchema(
            claim_id=claim_id,
            source_sentence=source,
            indicator="출생아 수",
            value=8.7,
            unit="%",
            time="2025",
            frequency="Y",
            comparison={"type": "YEAR_OVER_YEAR"},
            calculation=calculation,
            condition={"direction": "INCREASE"},
            parse_status="AUTO_OK",
        ),
    )


def _write_inputs(tmp_path: Path) -> tuple[Path, Path]:
    registry = tmp_path / "registry.jsonl"
    records = [
        _record("SAFE", "1", "4월 출생아 수는 전년 같은 달보다 8.7% 증가했다."),
        _record("RANGE", "2", "1~4월 누적 출생아 수는 8.7% 증가했다."),
        _record("RECORD", "3", "4월 출생아 수 증가율은 역대 최고였다.", calculation="RECORD_HIGH"),
    ]
    registry.write_text(
        "".join(record.model_dump_json() + "\n" for record in records),
        encoding="utf-8",
    )
    ledger = tmp_path / "ledger.csv"
    with ledger.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["Claim번호", "현재문제묶음", "남은작업"])
        writer.writeheader()
        for claim_id in ("SAFE", "RANGE", "RECORD"):
            writer.writerow({
                "Claim번호": claim_id,
                "현재문제묶음": "COORDINATE",
                "남은작업": "NO_EVIDENCE_COORDINATE_CANDIDATE",
            })
    return registry, ledger


def test_cli_builds_only_safe_monthly_birth_growth_claim_and_audits_group(tmp_path: Path) -> None:
    from tools import build_birth_reporting_month_group as cli

    registry, ledger = _write_inputs(tmp_path)
    output_registry = tmp_path / "output.jsonl"
    audit_csv = tmp_path / "audit.csv"

    assert cli.main([
        str(registry), str(ledger), str(output_registry), str(audit_csv),
        "--limit", "20",
    ]) == 0

    payloads = [
        json.loads(line)
        for line in output_registry.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(payloads) == 1
    assert payloads[0]["claim"]["claim_id"] == "SAFE"
    assert payloads[0]["claim"]["time"] == "2025년 4월"
    assert payloads[0]["claim"]["frequency"] == "월"
    assert payloads[0]["slot_enrichment"]["recovery_method"] == "SOURCE_REPORTING_MONTH"

    with audit_csv.open(encoding="utf-8-sig", newline="") as handle:
        audit = list(csv.DictReader(handle))
    assert [row["Claim번호"] for row in audit] == ["SAFE", "RANGE", "RECORD"]
    assert audit[0]["복구판정"] == "공식조회대상"
    assert audit[1]["복구사유"] == "MONTH_RANGE_NOT_SUPPORTED"
    assert audit[2]["복구사유"] == "CALCULATION_TYPE_NOT_SUPPORTED"


def test_cli_selects_only_current_coordinate_rows(tmp_path: Path) -> None:
    from tools import build_birth_reporting_month_group as cli

    registry, ledger = _write_inputs(tmp_path)
    with ledger.open("a", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["Claim번호", "현재문제묶음", "남은작업"])
        writer.writerow({"Claim번호": "SAFE", "현재문제묶음": "완료", "남은작업": "완료"})

    output_registry = tmp_path / "output.jsonl"
    audit_csv = tmp_path / "audit.csv"
    assert cli.main([str(registry), str(ledger), str(output_registry), str(audit_csv)]) == 0

    assert output_registry.read_text(encoding="utf-8") == ""
