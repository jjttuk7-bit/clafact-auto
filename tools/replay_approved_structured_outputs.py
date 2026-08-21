"""Replay validated Structured Outputs through the canonical official KOSIS engine."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import date
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import Settings
from core.claim_parser import parse_claim
from core.official_engine_factory import OfficialEnginePaths
from core.official_engine_factory_v3 import build_official_evidence_service_v3
from schemas.claim import ClaimSchema


class _StaticExtractor:
    def __init__(self, claim: ClaimSchema) -> None:
        self.claim = claim

    def extract(self, source_sentence: str, **_: object) -> ClaimSchema:
        return self.claim


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
    article_dates = _article_dates(args.registry_path)
    source_rows = _jsonl(args.approved_results)
    service = build_official_evidence_service_v3(
        OfficialEnginePaths(
            Path("data/semantic_standard/concept_seed_v1.json"),
            Path("data/kosis_catalog/catalog_350.json"),
            [],
            [Path("data/kosis_snapshots/gold_standard_v1_metadata_manifest.json")],
        ),
        semantic_overlay_path=Path("data/semantic_standard/concept_overlay_v3.json"),
        catalog_overlay_path=Path("data/kosis_catalog/catalog_overlay_v2.json"),
        kosis_api_key=settings.kosis_api_key,
        live_time_budget_seconds=args.live_budget_seconds,
    )
    output = []
    for row in source_rows:
        claim_payload = row.get("claim")
        if not isinstance(claim_payload, dict):
            output.append(row)
            continue
        claim = ClaimSchema.model_validate(claim_payload)
        published_at = article_dates.get(str(row.get("article_id") or ""))
        if claim.parse_status == "AUTO_OK":
            claim = parse_claim(
                claim.source_sentence, _StaticExtractor(claim),
                article_published_at=published_at,
            )
        route = "KOSIS_PIPELINE_ELIGIBLE" if claim.parse_status == "AUTO_OK" else "STRUCTURAL_HOLD"
        resolution = service.resolve(claim, article_date=published_at) if route == "KOSIS_PIPELINE_ELIGIBLE" and published_at else None
        output.append({
            **{key: value for key, value in row.items() if key not in {"claim", "official_resolution", "admission_route"}},
            "claim": claim.model_dump(mode="json"),
            "admission_route": route,
            "official_resolution": _serialize(resolution),
        })
    args.output_dir.mkdir(parents=True, exist_ok=True)
    _write_jsonl(args.output_dir / "claim_verification_results.jsonl", output)
    report = _report(output, len(set((row.get("article_id"), row.get("parent_claim_id")) for row in source_rows)))
    (args.output_dir / "outcome_acceptance_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({"output_dir": str(args.output_dir), **report}, ensure_ascii=False))


def _article_dates(path: Path) -> dict[str, date]:
    return {
        str(row["article_id"]): date.fromisoformat(str(row["article_published_at"]))
        for row in _jsonl(path)
        if row.get("article_id") and row.get("article_published_at")
    }


def _serialize(resolution):
    if resolution is None:
        return None
    return {
        "concept": resolution.concept.model_dump(mode="json"),
        "candidate_count": len(resolution.candidates),
        "verdict": resolution.verdict.model_dump(mode="json"),
    }


def _terminal(row):
    resolution = row.get("official_resolution")
    if isinstance(resolution, dict):
        verdict = resolution.get("verdict") or {}
        return verdict.get("route_status", "HOLD"), verdict.get("reason_code")
    return "HOLD", row.get("admission_route")


def _report(rows, input_count):
    terminal = [_terminal(row) for row in rows]
    operational = {
        "KOSIS_CATALOG_UNAVAILABLE", "KOSIS_METADATA_UNAVAILABLE", "FETCH_FAILED",
        "EXTERNAL_PIPELINE_FAILED", "EXTERNAL_PIPELINE_TIMEOUT", "WORKER_RESULT_MISSING",
    }
    return {
        "input_registry_records": input_count,
        "derived_claims": len(rows),
        "terminal_route_counts": dict(Counter(status for status, _ in terminal)),
        "terminal_reason_counts": dict(Counter(reason for _, reason in terminal if reason)),
        "operational_failure_count": sum(reason in operational for _, reason in terminal),
        "all_claims_terminal": all(status in {"AUTO", "HOLD"} for status, _ in terminal),
        "all_multi_claims_reentered": all(row.get("recovery_action") == "MULTI_CLAIM_SPLIT" for row in rows),
        "official_resolution_count": sum(row.get("official_resolution") is not None for row in rows),
    }


def _jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_jsonl(path: Path, rows) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


if __name__ == "__main__":
    main()
