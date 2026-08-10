"""Run a bounded, read-only OpenAI-to-KOSIS verification pilot."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from config.settings import Settings
from core.claim_registry_loader import load_claim_registry
from core.controlled_registry_pilot import derive_controlled_pilot, write_pilot_artifacts
from core.e2e_batch_runner import run_e2e_batch, summarize_e2e_batch
from core.kosis_api_adapter import build_kosis_api_lookup
from core.openai_function_claim_extractor import OpenAIFunctionClaimExtractor
from core.verification_profile_loader import load_verification_profiles


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--profiles", required=True, type=Path)
    parser.add_argument("--standard", required=True, type=Path)
    parser.add_argument("--snapshot", action="append", type=Path, default=[])
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()

    if not args.execute:
        print(json.dumps({"execute": False, "requested_limit": args.limit}, ensure_ascii=False))
        return

    settings = Settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY_NOT_CONFIGURED")
    registry = load_claim_registry(args.registry)
    extractor = OpenAIFunctionClaimExtractor(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
    )
    pilot = derive_controlled_pilot(
        registry.records,
        extractor,
        args.standard,
        limit=args.limit,
    )
    paths = write_pilot_artifacts(pilot, args.registry, args.output_dir)
    api_lookup = build_kosis_api_lookup(settings.kosis_api_key) if settings.kosis_api_key else None
    results = run_e2e_batch(
        pilot.records,
        load_verification_profiles(args.profiles),
        pilot.concepts,
        snapshot_paths=args.snapshot,
        api_lookup=api_lookup,
    )
    results_path = args.output_dir / "e2e_results.jsonl"
    report_path = args.output_dir / "coverage_report.json"
    review_path = args.output_dir / "review_queue.jsonl"
    results_path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in results),
        encoding="utf-8",
    )
    report = summarize_e2e_batch(results)
    report.update(
        {
            "requested_limit": args.limit,
            "registry_load_errors": [
                {"line_number": error.line_number, "reason_code": error.reason_code}
                for error in registry.errors
            ],
            "derived_artifacts": {
                "registry": str(paths.registry_path),
                "concepts": str(paths.concepts_path),
                "extraction_report": str(paths.report_path),
            },
        }
    )
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    review_rows = [row for row in results if row.get("route_status") != "AUTO"]
    review_path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in review_rows),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "selected_records": len(pilot.records),
                "result_records": len(results),
                "review_records": len(review_rows),
                "coverage_report": str(report_path),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
