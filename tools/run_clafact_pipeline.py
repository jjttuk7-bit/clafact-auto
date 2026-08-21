"""Run the canonical target/context-aware CLAFACT Registry pipeline."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sys
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path: sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import Settings
from core.admission_recovery_batch_v3 import run_admission_recovery_batch_v3
from core.claim_extractor_factory import create_claim_extractor
from core.claim_registry_loader import load_claim_registry
from core.official_engine_factory import OfficialEnginePaths
from core.official_engine_factory_v3 import build_official_evidence_service_v3
from core.operational_error import OperationalStageError, run_operational_stage


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("registry_path", type=Path); parser.add_argument("output_dir", type=Path)
    parser.add_argument("--context-jsonl", type=Path)
    parser.add_argument("--standard", type=Path, default=Path("data/semantic_standard/concept_seed_v1.json"))
    parser.add_argument("--catalog", type=Path, default=Path("data/kosis_catalog/catalog_350.json"))
    parser.add_argument("--semantic-overlay", type=Path, default=Path("data/semantic_standard/concept_overlay_v3.json"))
    parser.add_argument("--catalog-overlay", type=Path, default=Path("data/kosis_catalog/catalog_overlay_v2.json"))
    parser.add_argument("--metadata-manifest", type=Path, action="append", default=[Path("data/kosis_snapshots/gold_standard_v1_metadata_manifest.json")])
    parser.add_argument("--as-of-metadata", type=Path, action="append", default=[])
    parser.add_argument("--live-budget-seconds", type=float, default=30.0)
    args = parser.parse_args(); settings = Settings()
    if not settings.kosis_api_key: parser.error("KOSIS_API_KEY is required")
    registry = load_claim_registry(args.registry_path)
    service = build_official_evidence_service_v3(
        OfficialEnginePaths(args.standard, args.catalog, args.as_of_metadata, args.metadata_manifest),
        semantic_overlay_path=args.semantic_overlay, catalog_overlay_path=args.catalog_overlay,
        kosis_api_key=settings.kosis_api_key, live_time_budget_seconds=args.live_budget_seconds,
    )
    extractor, contexts, rows = create_claim_extractor(settings), _load_context(args.context_jsonl), []
    for record in registry.records:
        try:
            rows.extend(run_operational_stage("PIPELINE", lambda record=record: run_admission_recovery_batch_v3([record], extractor=extractor, official_service=service, article_context_by_id=contexts)))
        except OperationalStageError as error: rows.append(_operational_hold(record, error))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    _write_jsonl(args.output_dir / "claim_verification_results.jsonl", rows)
    report = _coverage_report(rows, len(registry.records), registry.errors)
    (args.output_dir / "coverage_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output_dir": str(args.output_dir), **report}, ensure_ascii=False))


def _operational_hold(record, error):
    return {"article_id": record.article_id, "sentence_id": record.sentence_id, "parent_claim_id": record.claim.claim_id, "claim_id": record.claim.claim_id, "source_sentence": record.claim.source_sentence, "recovery_action": "NO_RECOVERY", "admission_route": "STRUCTURAL_HOLD", "terminal_status": "HOLD", "reason_code": f"{error.stage}_UNAVAILABLE", "diagnostic_id": error.diagnostic_id, "official_resolution": None}


def _terminal(row):
    resolution = row.get("official_resolution")
    if isinstance(resolution, dict) and isinstance(resolution.get("verdict"), dict):
        verdict = resolution["verdict"]; return str(verdict.get("route_status") or "HOLD"), verdict.get("reason_code")
    return str(row.get("terminal_status") or "HOLD"), row.get("reason_code") or row.get("admission_route")


def _coverage_report(rows, input_count, errors):
    terminal = [_terminal(row) for row in rows]
    return {"input_registry_records": input_count, "derived_claims": len(rows), "recovery_action_counts": dict(sorted(Counter(row["recovery_action"] for row in rows).items())), "admission_route_counts": dict(sorted(Counter(row["admission_route"] for row in rows).items())), "terminal_route_counts": dict(sorted(Counter(status for status, _ in terminal).items())), "terminal_reason_counts": dict(sorted(Counter(reason for _, reason in terminal if reason).items())), "official_resolution_count": sum(row.get("official_resolution") is not None for row in rows), "all_claims_terminal": all(status in {"AUTO", "HOLD"} for status, _ in terminal), "registry_load_errors": [error.model_dump(mode="json") for error in errors]}


def _load_context(path: Path | None) -> dict[str, str]:
    if path is None: return {}
    contexts = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        row: Any = json.loads(line); article_id = str(row.get("article_id") or "").strip() if isinstance(row, dict) else ""; text = (row.get("article_text") or row.get("body") or row.get("text") or row.get("context")) if isinstance(row, dict) else None
        if article_id and isinstance(text, str) and text.strip(): contexts[article_id] = text.strip()
    return contexts


def _write_jsonl(path, rows): path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


if __name__ == "__main__": main()
