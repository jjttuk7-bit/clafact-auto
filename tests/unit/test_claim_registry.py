from datetime import date
import csv
import json

import pytest

from core.claim_registry import (
    build_registry_from_source,
    build_registry_records,
    load_registry_source_rows,
    write_registry_artifacts,
)
from schemas.claim import ClaimSchema
from schemas.claim_registry import ClaimRegistryRecord


def test_registry_record_keeps_source_provenance_and_empty_claim_slots() -> None:
    record = ClaimRegistryRecord(
        article_id="A00715",
        sentence_id="2",
        article_published_at=date(2025, 3, 1),
        source_ref="03_KOSIS대상_1600건",
        source_metadata={"domain": "trade_customs", "route": "KOSIS_RETRIEVAL"},
        claim=ClaimSchema(
            claim_id="registry:A00715:2",
            source_sentence="관련 서비스를 제공하는 KT의 경우 설치 매장 수량이 3배 늘었다.",
            parse_status="HUMAN_REVIEW",
        ),
    )

    assert record.claim.claim_id == "registry:A00715:2"
    assert record.claim.indicator is None
    assert record.claim.value is None
    assert record.source_metadata["route"] == "KOSIS_RETRIEVAL"
    assert record.review_status == "UNREVIEWED"


def test_registry_builder_preserves_source_rows_and_reports_count_mismatch() -> None:
    records, report = build_registry_records(
        [
            {
                "article_id": "A00001",
                "sentence_id": "3",
                "sentence": "2025년 3월 취업자 수는 2858만9000명이었다.",
                "domain": "employment_labor",
                "route": "KOSIS_RETRIEVAL",
                "claim_indicator": "취업자 수",
                "claim_value": "28589000",
                "claim_unit": "명",
                "claim_time": "2025-03",
                "parse_review_status": "AUTO_OK",
            }
        ],
        source_ref="guard-recheck-v2.2.1",
        expected_count=1532,
    )

    assert records[0].claim.claim_id == "registry:guard-recheck-v2.2.1:A00001:3"
    assert records[0].claim.indicator == "취업자 수"
    assert records[0].claim.value == 28589000.0
    assert records[0].claim.parse_status == "AUTO_OK"
    assert records[0].source_metadata["domain"] == "employment_labor"
    assert report["actual_count"] == 1
    assert report["expected_count"] == 1532
    assert report["count_matches"] is False


def test_registry_builder_rejects_duplicate_article_sentence_keys() -> None:
    rows = [
        {"article_id": "A00001", "sentence_id": "3", "sentence": "첫 문장"},
        {"article_id": "A00001", "sentence_id": "3", "sentence": "중복 문장"},
    ]

    with pytest.raises(ValueError, match="Duplicate source key"):
        build_registry_records(rows, source_ref="fixture")


def test_registry_artifacts_write_jsonl_and_validation_report(tmp_path) -> None:
    records, report = build_registry_records(
        [{"article_id": "A00001", "sentence_id": "1", "sentence": "문장"}],
        source_ref="fixture",
        expected_count=1532,
    )

    jsonl_path, report_path = write_registry_artifacts(
        records, report, output_dir=tmp_path
    )

    payload = json.loads(jsonl_path.read_text(encoding="utf-8").strip())
    validation = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["article_id"] == "A00001"
    assert payload["claim"]["parse_status"] == "HUMAN_REVIEW"
    assert validation["count_matches"] is False


def test_source_loader_reads_csv_and_enriches_article_dates(tmp_path) -> None:
    source_path = tmp_path / "source.csv"
    date_path = tmp_path / "dates.csv"
    with source_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["article_id", "sentence_id", "sentence"])
        writer.writeheader()
        writer.writerow({"article_id": "A00001", "sentence_id": "1", "sentence": "문장"})
    with date_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["article_id", "date"])
        writer.writeheader()
        writer.writerow({"article_id": "A00001", "date": "2025-01-01"})

    rows = load_registry_source_rows(source_path, date_source_path=date_path)

    assert rows == [
        {
            "article_id": "A00001",
            "sentence_id": "1",
            "sentence": "문장",
            "article_published_at": "2025-01-01",
        }
    ]


def test_registry_build_from_source_writes_a_reproducible_artifact(tmp_path) -> None:
    source_path = tmp_path / "source.csv"
    with source_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["article_id", "sentence_id", "sentence"])
        writer.writeheader()
        writer.writerow({"article_id": "A00002", "sentence_id": "7", "sentence": "원천 문장"})

    jsonl_path, report_path = build_registry_from_source(
        source_path,
        source_ref="source-fixture",
        expected_count=1,
        output_dir=tmp_path / "registry",
    )

    assert jsonl_path.name == "claim_registry.jsonl"
    assert json.loads(report_path.read_text(encoding="utf-8"))["count_matches"] is True


def test_registry_builder_preserves_all_gold_standard_slots_and_claim_id() -> None:
    records, _ = build_registry_records(
        [
            {
                "article_id": "A00001",
                "sentence_id": "3",
                "article_date": "2025-04-01",
                "sentence": "2025년 3월 취업자 수는 전년 동월보다 13만5000명 늘었다.",
                "claim_id": "A00001_3",
                "indicator": "취업자 수",
                "value": 135000,
                "unit": "명",
                "time": "2025-03",
                "frequency": "M",
                "region": "전국",
                "population": "15세 이상",
                "dimension": "성별:전체",
                "comparison": '{"기준":"전년 동월 대비","방향":"증가"}',
                "calculation": '{"type":"DIFFERENCE"}',
                "condition": '{"계절조정":"원계열"}',
                "source_hint": "통계청",
                "parse_status": "AUTO_OK",
            }
        ],
        source_ref="gold_standard_v1",
        expected_count=1,
    )

    claim = records[0].claim
    assert claim.claim_id == "A00001_3"
    assert claim.comparison == {"기준": "전년 동월 대비", "방향": "증가"}
    assert claim.calculation == "DIFFERENCE"
    assert claim.condition == {"계절조정": "원계열"}
    assert claim.dimension == {"raw": "성별:전체"}
    assert records[0].article_published_at == date(2025, 4, 1)
