import csv
from datetime import date
from pathlib import Path

from core.official_run_csv import write_official_run_csv
from schemas.claim import ClaimSchema
from schemas.claim_registry import ClaimRegistryRecord


def test_csv_keeps_official_author_document_audit_fields(tmp_path: Path) -> None:
    record = ClaimRegistryRecord(
        article_id="A1", sentence_id="1", article_published_at=date(2025, 1, 4),
        source_ref="test",
        claim=ClaimSchema(
            claim_id="c1", source_sentence="라면 수출 증가율은 70.3%였다.",
            indicator="대미 라면 수출 증가율", value=70.3, unit="%", time="2024",
            calculation="GROWTH_RATE", parse_status="AUTO_OK",
        ),
    )
    result = {
        "claim_id": "c1",
        "terminal_status": "AUTO",
        "official_resolution": {
            "concept": {"canonical_name": "수출 증가율"},
            "candidates": [],
            "catalog_diagnostics": {"kosis_catalog_unavailable": 1, "official_author_fallback_attempted": 1},
            "official_author_evidence": {
                "status": "VERIFIED", "author_name": "농림축산식품부",
                "source_url": "https://www.mafra.go.kr/release/1",
                "retrieved_at": "2025-01-02T00:00:00Z", "content_hash": "a" * 64,
            },
            "verdict": {
                "verdict": "MATCH", "route_status": "AUTO", "reason_code": "WITHIN_TOLERANCE",
                "evidence_values": [70.3], "calculated_value": 70.3,
                "official_value_provenance": [], "execution_trace": {"events": [
                    {"stage": "CATALOG_SEARCH", "status": "HOLD", "reason_code": "KOSIS_CATALOG_UNAVAILABLE"},
                    {"stage": "OFFICIAL_AUTHOR_SEARCH", "status": "PASS", "reason_code": None},
                    {"stage": "OFFICIAL_AUTHOR_FETCH", "status": "PASS", "reason_code": None},
                    {"stage": "VERDICT", "status": "PASS", "reason_code": None},
                ]},
            },
        },
    }
    path = tmp_path / "results.csv"

    write_official_run_csv([record], [result], path, code_version="v1", data_version="d1")

    with path.open(encoding="utf-8-sig", newline="") as source:
        row = next(csv.DictReader(source))
    assert row["작성기관보조경로"] == "예"
    assert row["공식작성기관"] == "농림축산식품부"
    assert row["공식문서상태"] == "VERIFIED"
    assert row["공식문서URL"] == "https://www.mafra.go.kr/release/1"
    assert row["공식문서조회시각"] == "2025-01-02T00:00:00Z"
    assert row["공식문서해시"] == "a" * 64
    assert row["공식API조회여부"] == "예"
    assert row["중단단계"] == ""
