import csv
from datetime import date
import json
from pathlib import Path

from schemas.claim import ClaimSchema
from schemas.claim_registry import ClaimRegistryRecord


def _record(claim_id: str, sentence_id: str, source: str) -> ClaimRegistryRecord:
    return ClaimRegistryRecord(
        article_id="A1",
        sentence_id=sentence_id,
        article_published_at=date(2025, 7, 2),
        source_ref="test",
        source_metadata={"missing_slots": "time"},
        claim=ClaimSchema(
            claim_id=claim_id,
            source_sentence=source,
            indicator="소비자물가 상승률",
            value=2.2,
            unit="%",
            time=None,
            calculation="DIRECT_VALUE",
            parse_status="HOLD",
            parse_reason=None,
        ),
    )


def _write_inputs(tmp_path: Path) -> tuple[Path, Path]:
    registry = tmp_path / "registry.jsonl"
    records = [
        _record("C1", "1", "6월 소비자물가 상승률은 2.2%였다."),
        _record("C2", "2", "6월 25일 소비자물가 상승률은 2.2%였다."),
    ]
    registry.write_text(
        "".join(record.model_dump_json() + "\n" for record in records),
        encoding="utf-8",
    )
    ledger = tmp_path / "ledger.csv"
    with ledger.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "Claim번호", "대표문제", "남은작업", "12개항목상태",
        ])
        writer.writeheader()
        for claim_id in ("C1", "C2"):
            writer.writerow({
                "Claim번호": claim_id,
                "대표문제": "CONTEXT",
                "남은작업": "CONTEXT_REQUIRED",
                "12개항목상태": (
                    "indicator=SOURCE | value=SOURCE | unit=SOURCE | "
                    "time=MISSING | calculation=SOURCE"
                ),
            })
    return registry, ledger


def test_cli_builds_only_safe_registry_and_audits_every_candidate(tmp_path: Path) -> None:
    from tools import build_explicit_previous_month_group as cli

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
    assert payloads[0]["claim"]["claim_id"] == "C1"
    assert payloads[0]["claim"]["time"] == "2025년 6월"
    assert payloads[0]["claim"]["parse_status"] == "AUTO_OK"
    assert payloads[0]["slot_enrichment"]["parent_claim_id"] == "C1"
    assert payloads[0]["slot_enrichment"]["recovery_method"] == "EXPLICIT_PREVIOUS_MONTH"

    with audit_csv.open(encoding="utf-8-sig", newline="") as handle:
        audit = list(csv.DictReader(handle))
    assert len(audit) == 2
    assert audit[0]["복구판정"] == "공식조회대상"
    assert audit[0]["복구시점"] == "2025년 6월"
    assert audit[1]["복구판정"] == "보류"
    assert audit[1]["복구사유"] == "UNSAFE_EXPLICIT_MONTH"


def test_limit_counts_admitted_claims_not_earlier_unsafe_candidates(tmp_path: Path) -> None:
    from tools import build_explicit_previous_month_group as cli

    registry, ledger = _write_inputs(tmp_path)
    payloads = registry.read_text(encoding="utf-8").splitlines()
    registry.write_text("\n".join(reversed(payloads)) + "\n", encoding="utf-8")
    output_registry = tmp_path / "output.jsonl"
    audit_csv = tmp_path / "audit.csv"

    assert cli.main([
        str(registry), str(ledger), str(output_registry), str(audit_csv),
        "--limit", "1",
    ]) == 0

    output = [
        json.loads(line)
        for line in output_registry.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert [row["claim"]["claim_id"] for row in output] == ["C1"]
    with audit_csv.open(encoding="utf-8-sig", newline="") as handle:
        audit = list(csv.DictReader(handle))
    assert [row["Claim번호"] for row in audit] == ["C2", "C1"]
