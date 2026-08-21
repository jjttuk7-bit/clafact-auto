"""Recover Admission-held registry claims through the shared live KOSIS engine."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
import sys
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import Settings
from core.admission_recovery_batch import run_admission_recovery_batch
from core.claim_extractor_factory import create_claim_extractor
from core.claim_registry_loader import load_claim_registry
from core.official_engine_factory import OfficialEnginePaths, build_official_evidence_service


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("registry_path", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--context-jsonl", type=Path)
    parser.add_argument("--standard", type=Path, default=Path("data/semantic_standard/concept_seed_v1.json"))
    parser.add_argument("--catalog", type=Path, default=Path("data/kosis_catalog/catalog_350.json"))
    parser.add_argument("--metadata-manifest", type=Path, action="append", default=[Path("data/kosis_snapshots/gold_standard_v1_metadata_manifest.json")])
    parser.add_argument("--as-of-metadata", type=Path, action="append", default=[])
    parser.add_argument("--live-budget-seconds", type=float, default=45.0)
    args = parser.parse_args()
    settings = Settings()
    if not settings.kosis_api_key:
        parser.error("KOSIS_API_KEY is required")
    registry = load_claim_registry(args.registry_path)
    service = build_official_evidence_service(
        OfficialEnginePaths(args.standard, args.catalog, args.as_of_metadata, args.metadata_manifest),
        kosis_api_key=settings.kosis_api_key,
        live_time_budget_seconds=args.live_budget_seconds,
    )
    rows = run_admission_recovery_batch(
        registry.records, extractor=create_claim_extractor(settings), official_service=service,
        article_context_by_id=_load_context(args.context_jsonl),
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "admission_recovery_results.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8"
    )
    report = {
        "input_registry_records": len(registry.records), "derived_claims": len(rows),
        "recovery_action_counts": dict(sorted(Counter(row["recovery_action"] for row in rows).items())),
        "admission_route_counts": dict(sorted(Counter(row["admission_route"] for row in rows).items())),
        "official_resolution_count": sum(row["official_resolution"] is not None for row in rows),
        "registry_load_errors": [error.model_dump(mode="json") for error in registry.errors],
    }
    (args.output_dir / "coverage_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output_dir": str(args.output_dir), **report}, ensure_ascii=False))


def _load_context(path: Path | None) -> dict[str, str]:
    if path is None: return {}
    context: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        row: Any = json.loads(line)
        if not isinstance(row, dict): continue
        article_id = str(row.get("article_id") or "").strip()
        article_text = row.get("article_text") or row.get("body") or row.get("text")
        if article_id and isinstance(article_text, str) and article_text.strip(): context[article_id] = article_text.strip()
    return context


if __name__ == "__main__": main()
