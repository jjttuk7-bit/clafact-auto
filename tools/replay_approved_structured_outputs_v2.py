"""Replay validated 12-slot Claims without resampling or overwriting them."""

from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import Settings
from core.claim_contract import assess_claim_contract
from core.claim_time_resolver import resolve_relative_time
from core.deterministic_slot_enricher import apply_explicit_slots
from core.official_engine_factory import OfficialEnginePaths
from core.official_engine_factory_v3 import build_official_evidence_service_v3
from schemas.claim import ClaimSchema
from tools.replay_approved_structured_outputs import (
    _article_dates, _jsonl, _report, _serialize, _write_jsonl,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("approved_results", type=Path)
    parser.add_argument("registry_path", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--live-budget-seconds", type=float, default=45.0)
    args = parser.parse_args()
    settings = Settings()
    if not settings.kosis_api_key:
        parser.error("KOSIS_API_KEY is required")
    dates = _article_dates(args.registry_path)
    source_rows = _jsonl(args.approved_results)
    service = build_official_evidence_service_v3(
        OfficialEnginePaths(
            Path("data/semantic_standard/concept_seed_v1.json"),
            Path("data/kosis_catalog/catalog_350.json"), [],
            [Path("data/kosis_snapshots/gold_standard_v1_metadata_manifest.json")],
        ),
        semantic_overlay_path=Path("data/semantic_standard/concept_overlay_v3.json"),
        catalog_overlay_path=Path("data/kosis_catalog/catalog_overlay_v2.json"),
        kosis_api_key=settings.kosis_api_key,
        live_time_budget_seconds=args.live_budget_seconds,
    )
    output = []
    for row in source_rows:
        payload = row.get("claim")
        if not isinstance(payload, dict):
            output.append(row)
            continue
        claim = ClaimSchema.model_validate(payload)
        published_at = dates.get(str(row.get("article_id") or ""))
        if claim.parse_status == "AUTO_OK":
            claim = resolve_relative_time(claim, published_at)
            claim = apply_explicit_slots(claim)
            decision = assess_claim_contract(claim)
            if decision.status == "HOLD":
                claim = claim.model_copy(update={"parse_status": "HOLD", "parse_reason": decision.reason_code})
        route = "KOSIS_PIPELINE_ELIGIBLE" if claim.parse_status == "AUTO_OK" else "STRUCTURAL_HOLD"
        resolution = service.resolve(claim, article_date=published_at) if route == "KOSIS_PIPELINE_ELIGIBLE" and published_at else None
        output.append({
            **{key: value for key, value in row.items() if key not in {"claim", "official_resolution", "admission_route"}},
            "claim": claim.model_dump(mode="json"), "admission_route": route,
            "official_resolution": _serialize(resolution),
        })
    args.output_dir.mkdir(parents=True, exist_ok=True)
    _write_jsonl(args.output_dir / "claim_verification_results.jsonl", output)
    report = _report(output, len(set((row.get("article_id"), row.get("parent_claim_id")) for row in source_rows)))
    (args.output_dir / "outcome_acceptance_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({"output_dir": str(args.output_dir), **report}, ensure_ascii=False))


if __name__ == "__main__":
    main()
