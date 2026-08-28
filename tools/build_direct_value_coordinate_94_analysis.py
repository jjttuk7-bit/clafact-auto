"""Classify all 94 coordinate failures and build their canonical rerun Registry."""

from __future__ import annotations

import argparse
import csv
from hashlib import sha256
import json
from pathlib import Path
import sys
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.direct_value_coordinate_94_analysis import analyze_coordinate_94
from core.direct_value_coordinate_94_scope import build_coordinate_94_scope


DEFAULT_EVALUATION = PROJECT_ROOT / "deliverables" / "CLAFACT_AUTO_직접값176_전체좌표탐색_20260828" / "CLAFACT_AUTO_직접값176_단계별평가표.csv"
DEFAULT_LIVE = PROJECT_ROOT / "artifacts" / "direct_value_coordinate_spec_176_20260828" / "live_run" / "claim_verification_results_final.jsonl"
DEFAULT_REGISTRY = PROJECT_ROOT / "artifacts" / "direct_value_coordinate_spec_176_20260828" / "ready_registry.jsonl"
DEFAULT_OUTPUT = PROJECT_ROOT / "artifacts" / "direct_value_coordinate_94_20260828"


def build_analysis_artifacts(
    evaluation_csv: Path,
    live_results_jsonl: Path,
    ready_registry_jsonl: Path,
    output_dir: Path,
    *,
    expected_count: int = 94,
) -> dict[str, object]:
    with evaluation_csv.open("r", encoding="utf-8-sig", newline="") as handle:
        evaluation_rows = list(csv.DictReader(handle))
    live_rows = _read_jsonl(live_results_jsonl)
    live_by_id = {_result_id(row): row for row in live_rows if _result_id(row)}
    source_fallbacks = {
        claim_id: str((row.get("claim") or {}).get("source_sentence") or "")
        for claim_id, row in live_by_id.items()
        if isinstance(row.get("claim"), dict)
    }
    scope = build_coordinate_94_scope(
        evaluation_rows,
        expected_count=expected_count,
        source_fallbacks=source_fallbacks,
    )
    scoped_live = [live_by_id[record.claim_id] for record in scope.records if record.claim_id in live_by_id]
    analysis = analyze_coordinate_94(scope, scoped_live)

    registry_rows = _read_jsonl(ready_registry_jsonl)
    registry_by_id: dict[str, dict[str, Any]] = {}
    for row in registry_rows:
        claim = row.get("claim") if isinstance(row.get("claim"), dict) else {}
        claim_id = str(claim.get("claim_id") or "")
        if claim_id:
            if claim_id in registry_by_id:
                raise ValueError(f"DIRECT_VALUE_COORDINATE_94_REGISTRY_NOT_UNIQUE:{claim_id}")
            registry_by_id[claim_id] = row
    missing = [record.claim_id for record in scope.records if record.claim_id not in registry_by_id]
    if missing:
        raise ValueError(f"DIRECT_VALUE_COORDINATE_94_REGISTRY_MISSING:{'|'.join(missing)}")
    rerun_registry = [registry_by_id[record.claim_id] for record in scope.records]

    output_dir.mkdir(parents=True, exist_ok=True)
    scope_path = output_dir / "scope.json"
    classification_path = output_dir / "classification.csv"
    registry_path = output_dir / "input_registry.jsonl"
    scope_path.write_text(
        json.dumps(scope.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with classification_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(analysis.rows[0]))
        writer.writeheader()
        writer.writerows(analysis.rows)
    registry_path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rerun_registry),
        encoding="utf-8",
    )
    summary = {
        "scope_count": len(scope.records),
        "rerun_registry_count": len(rerun_registry),
        "primary_cause_counts": analysis.primary_cause_counts,
        "rule_family_counts": analysis.rule_family_counts,
        "scope_manifest_sha256": scope.manifest_sha256,
        "evaluation_input_sha256": _sha256(evaluation_csv),
        "live_input_sha256": _sha256(live_results_jsonl),
        "registry_input_sha256": _sha256(ready_registry_jsonl),
        "classification_sha256": _sha256(classification_path),
        "rerun_registry_sha256": _sha256(registry_path),
    }
    (output_dir / "analysis_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _result_id(row: dict[str, Any]) -> str:
    return str(row.get("parent_claim_id") or row.get("claim_id") or "")


def _sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evaluation", type=Path, default=DEFAULT_EVALUATION)
    parser.add_argument("--live-results", type=Path, default=DEFAULT_LIVE)
    parser.add_argument("--ready-registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--expected-count", type=int, default=94)
    args = parser.parse_args()
    summary = build_analysis_artifacts(
        args.evaluation,
        args.live_results,
        args.ready_registry,
        args.output_dir,
        expected_count=args.expected_count,
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
