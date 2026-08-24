from __future__ import annotations

import csv
from datetime import date
import json
from pathlib import Path

from core.claim_issue_subclassification import classify_issue_subclass
from core.consolidated_claim_ledger import discover_updates
from core.official_run_csv import write_official_run_csv
from schemas.claim import ClaimSchema
from schemas.claim_registry import ClaimRegistryRecord


def _record() -> ClaimRegistryRecord:
    return ClaimRegistryRecord(
        article_id="A1",
        sentence_id="1",
        article_published_at=date(2025, 1, 1),
        source_ref="test",
        claim=ClaimSchema(
            claim_id="C1",
            source_sentence="2024년 고용률은 70%였다.",
            indicator="고용률",
            value=70,
            unit="%",
            time="2024",
            frequency="년",
            calculation="DIRECT_VALUE",
            parse_status="AUTO_OK",
        ),
    )


def _canonical_result() -> dict[str, object]:
    return {
        "article_id": "A1",
        "sentence_id": "1",
        "parent_claim_id": "C1",
        "claim_id": "C1",
        "terminal_status": "HOLD",
        "reason_code": "NO_HARD_GUARD_CANDIDATE",
        "stage_results": [{"finished_at": "2026-08-24T10:00:00+09:00"}],
        "official_resolution": {
            "concept": {"canonical_name": "고용률"},
            "candidates": [{"tbl_id": "T1"}],
            "catalog_diagnostics": {
                "attempted_queries": 1,
                "hard_guard_candidate_count": 3,
                "hard_guard_passed_count": 0,
                "hard_guard_reject_FREQUENCY_CONFLICT": 2,
                "hard_guard_reject_UNIT_CONFLICT": 1,
            },
            "verdict": {
                "route_status": "HOLD",
                "reason_code": "NO_HARD_GUARD_CANDIDATE",
                "execution_trace": {
                    "events": [{
                        "stage": "HARD_GUARD",
                        "status": "HOLD",
                        "reason_code": "NO_HARD_GUARD_CANDIDATE",
                    }]
                },
                "evidence_cells": [],
                "official_value_provenance": [],
            },
        },
    }


def test_official_csv_records_actual_hard_guard_reject_counts(tmp_path: Path) -> None:
    output = tmp_path / "official.csv"

    write_official_run_csv(
        [_record()], [_canonical_result()], output,
        code_version="v1", data_version="d1",
    )

    row = next(csv.DictReader(output.open(encoding="utf-8-sig", newline="")))
    assert row["조건검사탈락사유"] == "FREQUENCY_CONFLICT:2 | UNIT_CONFLICT:1"


def test_canonical_update_preserves_hard_guard_reject_counts(tmp_path: Path) -> None:
    output = tmp_path / "run" / "claim_verification_results.jsonl"
    output.parent.mkdir()
    output.write_text(
        json.dumps(_canonical_result(), ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    update = discover_updates([tmp_path], {"C1"}, {})[0]

    assert update.hard_guard_rejections == (
        "FREQUENCY_CONFLICT:2 | UNIT_CONFLICT:1"
    )


def test_actual_hard_guard_rejects_replace_generic_alias_classification() -> None:
    base = {
        "Claim번호": "C1",
        "원문": "2024년 고용률은 70%였다.",
        "남은작업": "NO_HARD_GUARD_CANDIDATE",
        "현재문제묶음": "HARD_GUARD",
        "최신결과사유": "NO_HARD_GUARD_CANDIDATE",
        "최신결과단계": "HARD_GUARD",
        "12개항목상태": "time=SOURCE | unit=SOURCE",
    }

    period = classify_issue_subclass({
        **base,
        "최신조건탈락사유": "FREQUENCY_CONFLICT:2 | TIME_NOT_AVAILABLE:1",
    })
    unit = classify_issue_subclass({
        **base,
        "최신조건탈락사유": "UNIT_CONFLICT:3",
    })
    dimension = classify_issue_subclass({
        **base,
        "최신조건탈락사유": "DIMENSION_MEMBER_CONFLICT:4",
    })
    metadata = classify_issue_subclass({
        **base,
        "최신조건탈락사유": "METADATA_INCOMPLETE:5",
    })

    assert period.code == "HARD_GUARD_PERIOD"
    assert unit.code == "HARD_GUARD_UNIT_VALUE"
    assert dimension.code == "HARD_GUARD_DIMENSION"
    assert metadata.code == "OFFICIAL_METADATA_LOOKUP"
