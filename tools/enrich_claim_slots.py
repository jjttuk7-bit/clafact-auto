"""Run a bounded live Structured Output enrichment batch for Claim Registry records."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from config.settings import Settings
from core.claim_extractor_factory import create_claim_extractor
from core.claim_slot_enrichment_batch import enrich_auto_registry_records
from core.secret_fingerprint import describe_secret_fingerprint


def add_run_metadata(
    summary: dict[str, object],
    *,
    provider: str,
    openai_api_key: str | None,
    requested_limit: int,
    source_registry: str,
) -> dict[str, object]:
    """Attach reproducibility metadata without persisting an API key."""
    result = dict(summary)
    result.update(
        {
            "provider": provider,
            "requested_limit": requested_limit,
            "source_registry": source_registry,
        }
    )
    if provider == "openai":
        result["openai_api_key_fingerprint"] = describe_secret_fingerprint(openai_api_key)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--limit", required=True, type=int)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if args.limit < 1:
        raise ValueError("--limit must be at least 1")

    records = [
        json.loads(line)
        for line in args.registry.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    selected = [
        record for record in records if record["claim"]["parse_status"] == "AUTO_OK"
    ][: args.limit]
    if not args.execute:
        print(json.dumps({"selected_records": len(selected), "execute": False}))
        return

    settings = Settings()
    extractor = create_claim_extractor(settings)
    enriched_records, summary = enrich_auto_registry_records(selected, extractor)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    records_path = args.output_dir / "enriched_claims.jsonl"
    summary_path = args.output_dir / "enrichment_summary.json"
    records_path.write_text(
        "\n".join(
            json.dumps(record, ensure_ascii=False, sort_keys=True)
            for record in enriched_records
        )
        + ("\n" if enriched_records else ""),
        encoding="utf-8",
    )
    summary = add_run_metadata(
        summary,
        provider=settings.claim_provider,
        openai_api_key=settings.openai_api_key,
        requested_limit=args.limit,
        source_registry=str(args.registry),
    )
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"Enriched records: {records_path}")
    print(f"Summary: {summary_path}")


if __name__ == "__main__":
    main()