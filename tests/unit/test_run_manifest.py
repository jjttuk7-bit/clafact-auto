from pathlib import Path

import pytest

from core.run_manifest import build_run_manifest


def test_manifest_records_hashes_versions_and_explicit_count_reconciliation(tmp_path: Path) -> None:
    source = tmp_path / "claims.jsonl"
    source.write_text('{"claim_id":"A"}\n', encoding="utf-8")

    manifest = build_run_manifest(
        run_id="run-001",
        inputs={"claim_registry": source},
        versions={
            "dataset_version": "registry-v1",
            "preprocess_version": "1.0",
            "claim_schema_version": "1.0",
            "semantic_standard_version": "seed-v1",
            "kosis_catalog_version": "catalog-v1",
            "matching_version": "profile-v1",
            "calculation_version": "calc-v1",
        },
        reconciliation={"target_count": 1532, "structured_count": 1531, "raw_count": 1600, "selection_rule": "explicit"},
        code_revision="abc123",
    )

    assert manifest["run_id"] == "run-001"
    assert manifest["inputs"]["claim_registry"]["sha256"]
    assert manifest["versions"]["calculation_version"] == "calc-v1"
    assert manifest["reconciliation"]["target_count"] == 1532
    assert manifest["code_revision"] == "abc123"


def test_manifest_rejects_missing_reconciliation_field(tmp_path: Path) -> None:
    source = tmp_path / "claims.jsonl"
    source.write_text('', encoding="utf-8")

    with pytest.raises(ValueError, match="selection_rule"):
        build_run_manifest(
            run_id="run-001",
            inputs={"claim_registry": source},
            versions={"dataset_version": "v"},
            reconciliation={"target_count": 1532, "structured_count": 1531, "raw_count": 1600},
            code_revision="abc123",
        )
