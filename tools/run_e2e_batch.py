"""Write reproducible E2E batch results and coverage report from local inputs."""

import argparse
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from config.settings import Settings
from core.claim_registry_loader import load_claim_registry
from core.deterministic_slot_enrichment_batch import (
    build_deterministic_enrichment_report,
    enrich_registry_records_deterministically,
)
from core.e2e_batch_runner import run_e2e_batch, summarize_e2e_batch
from core.kosis_api_adapter import build_kosis_api_lookup
from core.profile_priority_queue import build_profile_priority_queue
from core.review_queue_builder import build_review_queues
from core.verification_profile_loader import load_verification_profiles
from schemas.concept import StandardConceptSchema
from schemas.claim_registry import ClaimRegistryRecord
from schemas.evidence import EvidenceCellSchema


def run(
    registry_path: Path,
    profiles_path: Path,
    concepts_path: Path,
    output_dir: Path,
    *,
    additional_profile_paths: tuple[Path, ...] = (),
    snapshot_paths: tuple[Path, ...] = (),
    api_lookup: Callable[[EvidenceCellSchema], list[dict[str, Any]]] | None = None,
) -> tuple[Path, Path]:
    registry = load_claim_registry(registry_path)
    enriched_rows, _ = enrich_registry_records_deterministically(
        record.model_dump(mode="json") for record in registry.records
    )
    records = [ClaimRegistryRecord.model_validate(row) for row in enriched_rows]
    profiles = [
        profile
        for path in (profiles_path, *additional_profile_paths)
        for profile in load_verification_profiles(path)
    ]
    concepts_payload = json.loads(concepts_path.read_text(encoding="utf-8"))
    concepts = {
        (row["article_id"], row["sentence_id"]): StandardConceptSchema.model_validate(row["concept"])
        for row in concepts_payload
    }
    results = run_e2e_batch(
        records,
        profiles,
        concepts,
        snapshot_paths=snapshot_paths,
        api_lookup=api_lookup,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    results_path = output_dir / "e2e_results.jsonl"
    report_path = output_dir / "coverage_report.json"
    results_path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in results),
        encoding="utf-8",
    )
    profile_queue = build_profile_priority_queue(
        results,
        [record.model_dump(mode="json") for record in records],
    )
    (output_dir / "profile_review_priority_queue.json").write_text(
        json.dumps(profile_queue, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    review_queues, review_summary = build_review_queues(
        results,
        {record.claim.claim_id: record for record in records},
    )
    review_dir = output_dir / "review_queues"
    review_dir.mkdir(exist_ok=True)
    for stale_queue in review_dir.glob("*.jsonl"):
        stale_queue.unlink()
    for queue_type, rows in review_queues.items():
        (review_dir / f"{queue_type}.jsonl").write_text(
            "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
            encoding="utf-8",
        )
    (review_dir / "summary.json").write_text(
        json.dumps(review_summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "deterministic_enrichment_report.json").write_text(
        json.dumps(build_deterministic_enrichment_report(enriched_rows), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    report = summarize_e2e_batch(results)
    report["registry_load_errors"] = [
        {"line_number": error.line_number, "reason_code": error.reason_code}
        for error in registry.errors
    ]
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return results_path, report_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("registry_path", type=Path)
    parser.add_argument("profiles_path", type=Path)
    parser.add_argument("concepts_path", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--profile", dest="additional_profiles", type=Path, action="append", default=[])
    parser.add_argument("--snapshot", dest="snapshots", type=Path, action="append", default=[])
    parser.add_argument("--live-kosis", action="store_true", help="Use the read-only KOSIS API for confirmed Profile coordinates.")
    arguments = parser.parse_args()
    api_lookup = None
    if arguments.live_kosis:
        settings = Settings()
        if not settings.kosis_api_key:
            parser.error("--live-kosis requires KOSIS_API_KEY")
        api_lookup = build_kosis_api_lookup(settings.kosis_api_key)
    run(
        arguments.registry_path,
        arguments.profiles_path,
        arguments.concepts_path,
        arguments.output_dir,
        additional_profile_paths=tuple(arguments.additional_profiles),
        snapshot_paths=tuple(arguments.snapshots),
        api_lookup=api_lookup,
    )


