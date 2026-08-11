"""Run the standard profile-free E2E batch pipeline."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

from config.settings import Settings
from core.claim_extractor_factory import create_claim_extractor
from core.claim_parser import parse_claim
from core.claim_registry_loader import load_claim_registry
from core.claim_time_resolver import resolve_relative_time
from core.data_loader import load_kosis_catalog, load_standard_concepts
from core.dynamic_e2e_batch_runner import run_dynamic_e2e_batch
from core.kosis_api_adapter import build_kosis_api_lookup
from core.kosis_live_catalog import KosisLiveCatalogSearch
from core.review_queue_builder import build_review_queues
from schemas.claim import ClaimSchema
from schemas.evidence import EvidenceCellSchema


def run(
    registry_path: Path,
    standard_path: Path,
    output_dir: Path,
    *,
    catalog_path: Path = Path("data/kosis_catalog/catalog_350.json"),
    snapshot_paths: tuple[Path, ...] = (),
    api_lookup: Callable[[EvidenceCellSchema], list[dict[str, Any]]] | None = None,
    kosis_api_key: str | None = None,
    live_search: KosisLiveCatalogSearch | None = None,
    claim_reparser: Callable[[ClaimSchema, date], ClaimSchema] | None = None,
) -> tuple[Path, Path]:
    """Write a dynamic KOSIS batch run with typed, stage-specific review queues."""
    registry = load_claim_registry(registry_path)
    results = run_dynamic_e2e_batch(
        registry.records,
        load_standard_concepts(standard_path),
        load_kosis_catalog(catalog_path),
        snapshot_paths=snapshot_paths,
        api_lookup=api_lookup,
        kosis_api_key=kosis_api_key,
        live_search=live_search,
        claim_reparser=claim_reparser,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    results_path = output_dir / "e2e_results.jsonl"
    report_path = output_dir / "coverage_report.json"
    results_path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in results),
        encoding="utf-8",
    )
    review_queues, review_summary = build_review_queues(
        results, {record.claim.claim_id: record for record in registry.records}
    )
    review_dir = output_dir / "review_queues"
    review_dir.mkdir(exist_ok=True)
    for queue_type, rows in review_queues.items():
        (review_dir / f"{queue_type}.jsonl").write_text(
            "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
            encoding="utf-8",
        )
    (review_dir / "summary.json").write_text(
        json.dumps(review_summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
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
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return results_path, report_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("registry_path", type=Path)
    parser.add_argument("standard_path", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--catalog", type=Path, default=Path("data/kosis_catalog/catalog_350.json"))
    parser.add_argument("--snapshot", action="append", type=Path, default=[])
    parser.add_argument("--live-kosis", action="store_true")
    parser.add_argument("--skip-reparse-holds", action="store_true", help="Keep prior non-AUTO parse results without re-running 12-slot parsing.")
    args = parser.parse_args()

    settings = Settings()
    if args.live_kosis and not settings.kosis_api_key:
        parser.error("--live-kosis requires KOSIS_API_KEY")
    api_lookup = build_kosis_api_lookup(settings.kosis_api_key) if args.live_kosis else None
    claim_reparser = None
    if not args.skip_reparse_holds:
        extractor = create_claim_extractor(settings)

        def claim_reparser(claim: ClaimSchema, article_date: date) -> ClaimSchema:
            return resolve_relative_time(parse_claim(claim.source_sentence, extractor), article_date)

    results_path, report_path = run(
        args.registry_path,
        args.standard_path,
        args.output_dir,
        catalog_path=args.catalog,
        snapshot_paths=tuple(args.snapshot),
        api_lookup=api_lookup,
        kosis_api_key=settings.kosis_api_key if args.live_kosis else None,
        live_search=KosisLiveCatalogSearch(settings.kosis_api_key) if args.live_kosis else None,
        claim_reparser=claim_reparser,
    )
    print(json.dumps({"results_path": str(results_path), "report_path": str(report_path)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
