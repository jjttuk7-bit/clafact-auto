"""Run 12-slot reporting, exact Concept mapping, and KOSIS E2E from enriched rows."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from config.settings import Settings
from core.e2e_batch_runner import run_e2e_batch, summarize_e2e_batch
from core.kosis_api_adapter import build_kosis_api_lookup
from core.registry_batch_reporting import derive_registry_batch
from core.verification_profile_loader import load_verification_profiles


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--enriched", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--profiles", required=True, type=Path)
    parser.add_argument("--standard", required=True, type=Path)
    parser.add_argument("--snapshot", action="append", type=Path, default=[])
    args = parser.parse_args()

    rows = [json.loads(line) for line in args.enriched.read_text(encoding="utf-8").splitlines() if line.strip()]
    derivation = derive_registry_batch(rows, args.standard)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    _write_jsonl(args.output_dir / "derived_registry.jsonl", [record.model_dump(mode="json") for record in derivation.records])
    _write_json(args.output_dir / "concepts.json", [
        {"article_id": article_id, "sentence_id": sentence_id, "concept": concept.model_dump(mode="json")}
        for (article_id, sentence_id), concept in sorted(derivation.concepts.items())
    ])
    _write_json(args.output_dir / "structured_quality_report.json", derivation.quality_report)
    _write_jsonl(args.output_dir / "structured_review_queue.jsonl", derivation.review_queue)

    settings = Settings()
    lookup = build_kosis_api_lookup(settings.kosis_api_key) if settings.kosis_api_key else None
    results = run_e2e_batch(
        derivation.records,
        load_verification_profiles(args.profiles),
        derivation.concepts,
        snapshot_paths=args.snapshot,
        api_lookup=lookup,
    )
    _write_jsonl(args.output_dir / "e2e_results.jsonl", results)
    report = summarize_e2e_batch(results)
    report["structured_quality_report"] = "structured_quality_report.json"
    report["review_queue"] = "structured_review_queue.jsonl"
    _write_json(args.output_dir / "coverage_report.json", report)


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[object]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


if __name__ == "__main__":
    main()
