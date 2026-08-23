from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

from core.official_run_csv import write_official_run_csv
from schemas.claim import ClaimSchema
from schemas.claim_registry import ClaimRegistryRecord


def _record() -> ClaimRegistryRecord:
    return ClaimRegistryRecord(
        article_id="A1",
        sentence_id="1:multi:1",
        article_published_at=date(2025, 2, 15),
        source_ref="multi",
        source_metadata={"parent_claim_id": "parent-1"},
        claim=ClaimSchema(
            claim_id="child-1",
            source_sentence="고용률은 60%였다.",
            indicator="고용률",
            value=60.0,
            unit="%",
            time="2025-01",
            frequency="월",
            calculation="DIRECT_VALUE",
            parse_status="AUTO_OK",
        ),
    )


def _result() -> dict[str, object]:
    return {
        "claim_id": "child-1",
        "terminal_status": "AUTO",
        "reason_code": "WITHIN_TOLERANCE",
        "slot_audit": {
            "entries": [{"slot": "indicator", "status": "SOURCE", "value": "고용률"}]
        },
        "official_resolution": {
            "concept": {"standard_key": "employment_rate", "canonical_name": "고용률"},
            "candidates": [{"tbl_id": "DT_TEST"}],
            "catalog_diagnostics": {
                "attempted_queries": 3,
                "metadata_itm_attempted": 2,
                "metadata_prd_attempted": 2,
            },
            "verdict": {
                "verdict": "MATCH",
                "calculated_value": 60.0,
                "evidence_values": [60.0],
                "evidence_cells": [
                    {
                        "org_id": "101",
                        "tbl_id": "DT_TEST",
                        "itm_id": "T1",
                        "prd_se": "월",
                        "prd_de": "2025-01",
                        "dimension_codes": {"G": "00"},
                    }
                ],
                "official_value_provenance": [
                    {
                        "source": "API",
                        "source_url": "https://kosis.example/value",
                        "content_hash": "value-hash",
                        "publication": {
                            "status": "VERIFIED",
                            "source_url": "https://kostat.example/release",
                            "content_hash": "release-hash",
                        },
                    }
                ],
                "execution_trace": {
                    "events": [
                        {"stage": "CATALOG_SEARCH", "status": "PASS", "reason_code": None},
                        {"stage": "OFFICIAL_VALUE_FETCH", "status": "PASS", "reason_code": None},
                        {"stage": "VERDICT", "status": "PASS", "reason_code": None},
                    ]
                },
            },
        },
    }


def test_writes_one_auditable_korean_row_per_official_child(tmp_path: Path) -> None:
    output = tmp_path / "official.csv"

    write_official_run_csv(
        [_record()], [_result()], output, code_version="v1", data_version="d1"
    )

    row = next(csv.DictReader(output.open(encoding="utf-8-sig", newline="")))
    assert row["부모Claim번호"] == "parent-1"
    assert row["자식Claim번호"] == "child-1"
    assert row["공식API조회여부"] == "예"
    assert row["공식값조회성공"] == "예"
    assert row["공표확인"] == "확인"
    assert "통계표검색=통과" in row["단계별결과"]
    assert row["공식값URL"] == "https://kosis.example/value"
    assert row["공표URL"] == "https://kostat.example/release"
    assert row["응답해시"] == "value-hash"
    assert row["공표해시"] == "release-hash"
    assert row["판정"] == "MATCH"
    assert row["최종상태"] == "AUTO"


def test_holds_record_the_first_failed_stage_in_korean(tmp_path: Path) -> None:
    result = _result()
    result["terminal_status"] = "HOLD"
    result["reason_code"] = "NO_HARD_GUARD_CANDIDATE"
    verdict = result["official_resolution"]["verdict"]  # type: ignore[index]
    verdict["execution_trace"]["events"] = [  # type: ignore[index]
        {"stage": "CATALOG_SEARCH", "status": "PASS", "reason_code": None},
        {
            "stage": "HARD_GUARD",
            "status": "HOLD",
            "reason_code": "NO_HARD_GUARD_CANDIDATE",
        },
    ]
    verdict["official_value_provenance"] = []  # type: ignore[index]
    output = tmp_path / "hold.csv"

    write_official_run_csv(
        [_record()], [result], output, code_version="v1", data_version="d1"
    )

    row = next(csv.DictReader(output.open(encoding="utf-8-sig", newline="")))
    assert row["중단단계"] == "기본조건검사"
    assert row["중단사유"] == "NO_HARD_GUARD_CANDIDATE"
    assert row["공식값조회성공"] == "아니오"
