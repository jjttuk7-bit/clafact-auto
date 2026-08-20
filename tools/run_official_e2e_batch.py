"""Run a Registry slice through the shared live OfficialEvidenceService."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from config.settings import Settings`r`nfrom core.claim_applicability import annotate_result_rows
from core.claim_registry_loader import load_claim_registry
from core.official_e2e_batch_runner import run_official_e2e_batch
from core.official_engine_factory import OfficialEnginePaths, build_official_evidence_service
from core.review_queue_builder import build_review_queues


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("registry_path", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--standard", type=Path, default=Path("data/semantic_standard/concept_seed_v1.json"))
    parser.add_argument("--catalog", type=Path, default=Path("data/kosis_catalog/catalog_350.json"))
    parser.add_argument("--metadata-manifest", type=Path, action="append", default=[Path("data/kosis_snapshots/gold_standard_v1_metadata_manifest.json")])
    parser.add_argument("--as-of-metadata", type=Path, action="append", default=[])
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--live-budget-seconds", type=float, default=45.0)
    args = parser.parse_args()

    settings = Settings()
    if not settings.kosis_api_key:
        parser.error("KOSIS_API_KEY is required")
    registry = load_claim_registry(args.registry_path)
    service = build_official_evidence_service(
        OfficialEnginePaths(
            standard_path=args.standard,
            catalog_path=args.catalog,
            as_of_metadata_paths=args.as_of_metadata,
            metadata_manifest_paths=args.metadata_manifest,
        ),
        kosis_api_key=settings.kosis_api_key,
        live_time_budget_seconds=args.live_budget_seconds,
    )
    rows = annotate_result_rows(run_official_e2e_batch(registry.records, service, start=args.start, limit=args.limit))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "e2e_results.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8"
    )
    queues, queue_summary = build_review_queues(rows, {record.claim.claim_id: record for record in registry.records})
    queue_dir = args.output_dir / "review_queues"
    queue_dir.mkdir(exist_ok=True)
    for name, queue_rows in queues.items():
        (queue_dir / f"{name}.jsonl").write_text(
            "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in queue_rows), encoding="utf-8"
        )
    (queue_dir / "summary.json").write_text(json.dumps(queue_summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = {
        "total_records": len(rows),
        "route_counts": dict(sorted(Counter(row["route_status"] for row in rows).items())),`r`n        "applicability_counts": dict(sorted(Counter(row["applicability_diagnosis"]["label"] for row in rows).items())),
        "hold_reason_counts": dict(sorted(Counter(row["reason_code"] for row in rows if row["route_status"] != "AUTO").items())),
        "registry_load_errors": [error.model_dump(mode="json") for error in registry.errors],
    }
    (args.output_dir / "coverage_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output_dir": str(args.output_dir), **report}, ensure_ascii=False))


if __name__ == "__main__":
    main()

