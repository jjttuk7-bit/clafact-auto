"""Re-run structured Claims through the profile-free dynamic KOSIS pipeline."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from config.settings import Settings
from core.claim_registry_loader import load_claim_registry
from core.data_loader import load_kosis_catalog
from core.dynamic_e2e_batch_runner import run_dynamic_e2e_batch
from core.kosis_api_adapter import build_kosis_api_lookup
from schemas.concept import StandardConceptSchema


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("registry_path", type=Path)
    parser.add_argument("concepts_path", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--catalog", type=Path, default=Path("data/kosis_catalog/catalog_350.json"))
    parser.add_argument("--snapshot", action="append", type=Path, default=[])
    parser.add_argument("--live-kosis", action="store_true")
    args = parser.parse_args()

    registry = load_claim_registry(args.registry_path)
    concept_rows = json.loads(args.concepts_path.read_text(encoding="utf-8"))
    concepts = {
        (row["article_id"], row["sentence_id"]): StandardConceptSchema.model_validate(row["concept"])
        for row in concept_rows
    }
    settings = Settings()
    if args.live_kosis and not settings.kosis_api_key:
        parser.error("--live-kosis requires KOSIS_API_KEY")
    api_lookup = build_kosis_api_lookup(settings.kosis_api_key) if args.live_kosis else None
    results = run_dynamic_e2e_batch(
        registry.records,
        concepts,
        load_kosis_catalog(args.catalog),
        snapshot_paths=args.snapshot,
        api_lookup=api_lookup,
        kosis_api_key=settings.kosis_api_key if args.live_kosis else None,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "e2e_results.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in results), encoding="utf-8"
    )
    routes = Counter(row["route_status"] for row in results)
    reasons = Counter(row["reason_code"] for row in results if row.get("reason_code"))
    report = {
        "total_records": len(results),
        "route_counts": dict(sorted(routes.items())),
        "hold_reason_counts": dict(sorted(reasons.items())),
        "profile_dependency": "none",
        "registry_load_errors": [error.model_dump() for error in registry.errors],
    }
    (args.output_dir / "coverage_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({"output_dir": str(args.output_dir), **report}, ensure_ascii=False))


if __name__ == "__main__":
    main()
