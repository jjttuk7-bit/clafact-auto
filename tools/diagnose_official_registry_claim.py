"""Inspect safe KOSIS candidate, metadata, and Hard Guard diagnostics for one Registry Claim."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import Settings
from core.claim_registry_loader import load_claim_registry
from core.hard_guard import apply_hard_guard
from core.official_engine_factory import OfficialEnginePaths, build_official_evidence_service
from core.semantic_matcher import semantic_match


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("registry_path", type=Path)
    parser.add_argument("--article-id", required=True)
    parser.add_argument("--standard", type=Path, default=Path("data/semantic_standard/concept_seed_v1.json"))
    parser.add_argument("--catalog", type=Path, default=Path("data/kosis_catalog/catalog_350.json"))
    parser.add_argument(
        "--metadata-manifest",
        type=Path,
        action="append",
        default=[Path("data/kosis_snapshots/gold_standard_v1_metadata_manifest.json")],
    )
    parser.add_argument("--live-budget-seconds", type=float, default=10.0)
    args = parser.parse_args()

    settings = Settings()
    if not settings.kosis_api_key:
        parser.error("KOSIS_API_KEY is required")
    loaded = load_claim_registry(args.registry_path)
    matches = [record for record in loaded.records if record.article_id == args.article_id]
    if len(matches) != 1:
        parser.error(f"exactly one Registry record required; found {len(matches)}")
    record = matches[0]
    if record.article_published_at is None:
        parser.error("article_published_at is required")
    service = build_official_evidence_service(
        OfficialEnginePaths(
            standard_path=args.standard,
            catalog_path=args.catalog,
            as_of_metadata_paths=[],
            metadata_manifest_paths=args.metadata_manifest,
        ),
        kosis_api_key=settings.kosis_api_key,
        live_time_budget_seconds=args.live_budget_seconds,
    )
    resolution = service.resolve(record.claim, article_date=record.article_published_at)
    match_by_table = {
        item.candidate_tbl_id: item.model_dump(mode="json")
        for item in semantic_match(record.claim, resolution.candidates)
    }
    payload = {
        "article_id": record.article_id,
        "claim": record.claim.model_dump(mode="json"),
        "concept": resolution.concept.model_dump(mode="json"),
        "verdict": resolution.verdict.model_dump(mode="json"),
        "catalog_diagnostics": resolution.catalog_diagnostics,
        "candidates": [
            {
                "org_id": candidate.org_id,
                "tbl_id": candidate.tbl_id,
                "tbl_name": candidate.tbl_name,
                "metadata_status": candidate.metadata_status,
                "frequency": candidate.frequency,
                "unit_names": candidate.unit_names,
                "core_item_ids": candidate.core_item_ids,
                "core_item_names": candidate.core_item_names,
                "dimension_names": candidate.dimension_names,
                "hard_guard": apply_hard_guard(record.claim, candidate).model_dump(mode="json"),
                "semantic_match": match_by_table.get(candidate.tbl_id),
            }
            for candidate in resolution.candidates
        ],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
