"""Reparse only non-AUTO gold Claims into a source-preserving derived Registry."""

from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path

from config.settings import Settings
from core.claim_registry_loader import load_claim_registry
from core.claim_reparse_batch import reparse_non_auto_records
from core.openai_function_claim_extractor import OpenAIFunctionClaimExtractor


def validate_openai_reparse_settings(settings: Settings) -> None:
    """Require the explicitly approved OpenAI boundary for this derived Registry."""
    if settings.claim_provider.strip().casefold() != "openai":
        raise RuntimeError("OPENAI_PROVIDER_REQUIRED")
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY_NOT_CONFIGURED")
    if not settings.openai_model.strip():
        raise RuntimeError("OPENAI_MODEL_NOT_CONFIGURED")


def validate_reparse_summary(summary: dict[str, object]) -> None:
    """Never publish a partially failed Registry as a completed gold derivation."""
    if int(summary.get("reparse_errors", 0)) != 0:
        raise RuntimeError("CLAIM_REPARSE_BATCH_FAILED")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--workers", type=int, default=5)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if args.workers < 1:
        parser.error("--workers must be at least one")

    loaded = load_claim_registry(args.registry)
    if loaded.errors:
        parser.error(f"source Registry has {len(loaded.errors)} load errors")
    selected = sum(
        record.claim.parse_status != "AUTO_OK" for record in loaded.records
    )
    if not args.execute:
        print(json.dumps({
            "total_records": len(loaded.records),
            "selected_records": selected,
            "execute": False,
        }, ensure_ascii=False))
        return

    settings = Settings()
    validate_openai_reparse_settings(settings)
    extractor = OpenAIFunctionClaimExtractor(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
    )
    records, summary = reparse_non_auto_records(
        loaded.records,
        extractor,
        workers=args.workers,
    )
    validate_reparse_summary(summary)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    registry_path = args.output_dir / "claim_registry.jsonl"
    temporary_path = args.output_dir / "claim_registry.jsonl.tmp"
    temporary_path.write_text(
        "".join(
            json.dumps(record.model_dump(mode="json"), ensure_ascii=False, sort_keys=True)
            + "\n"
            for record in records
        ),
        encoding="utf-8",
    )
    temporary_path.replace(registry_path)

    report = {
        **summary,
        "provider": "openai",
        "model": settings.openai_model,
        "source_registry": str(args.registry),
        "source_registry_sha256": sha256(args.registry.read_bytes()).hexdigest(),
        "result_parse_status_counts": dict(sorted(Counter(
            record.claim.parse_status for record in records
        ).items())),
        "output_registry": str(registry_path),
    }
    report_path = args.output_dir / "reparse_report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "registry_path": str(registry_path),
        "report_path": str(report_path),
        "summary": summary,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
