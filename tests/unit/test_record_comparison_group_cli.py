import csv
import json
from datetime import date
from types import SimpleNamespace

import pytest

from core.unified_claim_pipeline import PipelineEntry
from schemas.claim import ClaimSchema
from schemas.claim_registry import ClaimRegistryRecord


def _record() -> ClaimRegistryRecord:
    claim = ClaimSchema(
        claim_id="record-parent",
        source_sentence="\uc218\ucd9c\uc561\uc740 100\uc5b5\ub2ec\ub7ec\ub85c \uc5ed\ub300 \ucd5c\ub300\uc600\ub2e4.",
        indicator="\uc218\ucd9c\uc561", value=100, unit="\uc5b5\ub2ec\ub7ec", time="2024\ub144",
        frequency="\ub144", comparison={"type": "RECORD_HIGH"}, calculation="DIRECT_VALUE",
        parse_status="HOLD", parse_reason="RECORD_COMPARISON_REQUIRES_SEPARATE_CLAIM",
    )
    return ClaimRegistryRecord(
        article_id="A1", sentence_id="1", article_published_at=date(2025, 1, 2),
        source_ref="test", claim=claim,
    )


class _Runtime:
    def verify_record(self, record, **kwargs):
        child = record.claim.model_copy(update={
            "claim_id": "record-child", "calculation": "RECORD_HIGH", "parse_status": "AUTO_OK",
            "parse_reason": None,
        })
        resolution = {
            "candidates": [{"org_id": "101", "tbl_id": "DT_TEST"}],
            "verdict": {
                "route_status": "AUTO", "reason_code": "RECORD_CONFIRMED",
                "record_comparison": {
                    "comparison_type": "RECORD_HIGH", "start_period": "2020",
                    "end_period": "2024", "observed_count": 5, "record_value": 100.0,
                    "record_unit": "\uc5b5\ub2ec\ub7ec", "record_periods": ["2024"],
                },
                "official_value_provenance": [{
                    "source_url": "https://kosis.kr/openapi", "content_hash": "hash-2024",
                    "source": "API", "publication": {"status": "VERIFIED"},
                }],
                "evidence_cells": [
                    {"org_id": "101", "tbl_id": "DT_TEST", "prd_de": "2020"},
                    {"org_id": "101", "tbl_id": "DT_TEST", "prd_de": "2024"},
                ],
                "execution_trace": {"events": [{"stage": "VERDICT", "status": "PASS"}]},
            },
        }
        return [PipelineEntry(
            parent_claim_id=record.claim.claim_id, claim=child,
            recovery_action="RECORD_COMPARISON_SPLIT", admission_route="KOSIS_PIPELINE_ELIGIBLE",
            terminal_status="AUTO", reason_code="RECORD_CONFIRMED", official_resolution=resolution,
        )]


def test_cli_rejects_unbounded_execution(tmp_path) -> None:
    from tools import run_record_comparison_group as cli

    with pytest.raises(SystemExit):
        cli.main([str(tmp_path / "registry.jsonl"), str(tmp_path / "out"), "--run-id", "run-1"])


def test_cli_rejects_more_than_twenty_claims(tmp_path) -> None:
    from tools import run_record_comparison_group as cli

    with pytest.raises(SystemExit):
        cli.main([
            str(tmp_path / "registry.jsonl"), str(tmp_path / "out"), "--run-id", "run-1",
            "--limit", "21",
        ])


def test_cli_runs_selected_record_group_and_writes_auditable_csv_jsonl(tmp_path, monkeypatch) -> None:
    from tools import run_record_comparison_group as cli

    registry_path = tmp_path / "registry.jsonl"
    registry_path.write_text(_record().model_dump_json() + "\n", encoding="utf-8")
    monkeypatch.setattr(cli, "Settings", lambda: SimpleNamespace(kosis_api_key="configured"))
    monkeypatch.setattr(cli, "build_canonical_pipeline", lambda *args, **kwargs: _Runtime())

    output_dir = tmp_path / "out"
    assert cli.main([
        str(registry_path), str(output_dir), "--run-id", "record-001",
        "--claim-id", "record-parent",
    ]) == 0

    jsonl_rows = [json.loads(line) for line in (output_dir / "record-001.jsonl").read_text(encoding="utf-8").splitlines()]
    with (output_dir / "record-001.csv").open(encoding="utf-8-sig", newline="") as handle:
        csv_rows = list(csv.DictReader(handle))

    assert len(jsonl_rows) == len(csv_rows) == 1
    row = csv_rows[0]
    assert row["before_parse_status"] == "HOLD"
    assert row["child_type"] == "RECORD_HIGH"
    assert row["after_status"] == "AUTO"
    assert row["after_reason"] == "RECORD_CONFIRMED"
    assert row["official_table"] == "101:DT_TEST"
    assert row["history_period_range"] == "2020~2024"
    assert row["requested_period_range"] == "2020~2024"
    assert row["requested_period_count"] == "2"
    assert row["observed_count"] == "5"
    assert row["record_periods"] == "2024"
    assert row["source_urls"] == "https://kosis.kr/openapi"
    assert row["response_hashes"] == "hash-2024"
    assert "VERDICT" in row["official_trace_json"]


def test_csv_does_not_overreport_mixed_api_and_snapshot_evidence() -> None:
    from tools.run_record_comparison_group import _csv_row

    row = _csv_row({
        "run_id": "mixed",
        "claim": {"calculation": "RECORD_HIGH"},
        "official_resolution": {
            "verdict": {
                "route_status": "AUTO",
                "evidence_cells": [
                    {"org_id": "101", "tbl_id": "DT", "prd_de": "2023"},
                    {"org_id": "101", "tbl_id": "DT", "prd_de": "2024"},
                ],
                "official_value_provenance": [
                    {"source": "API", "content_hash": "api", "publication": {"status": "VERIFIED"}},
                    {"source": "SNAPSHOT", "content_hash": "snapshot", "publication": {"status": "VERIFIED"}},
                ],
            },
        },
    })

    assert row["response_hashes"] == "api|snapshot"
    assert row["official_api_verified"] == "false"
