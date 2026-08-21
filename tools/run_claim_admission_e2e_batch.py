"""Route Registry candidates before running admitted Claims through live KOSIS E2E."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from config.settings import Settings
from core.claim_admission_e2e_batch_runner import run_claim_admission_e2e_batch
from core.claim_extractor_factory import create_claim_extractor
from core.claim_parser import parse_claim
from core.claim_registry_loader import load_claim_registry
from core.context_claim_reparse_batch import _limited_context
from core.explicit_numeric_slot import extract_explicit_numeric_slot
from core.official_engine_factory import OfficialEnginePaths, build_official_evidence_service
from core.openai_admission_router import OpenAIAdmissionRouter
from core.openai_function_claim_extractor import OpenAIClaimExtractorError
from schemas.claim import ClaimSchema
from schemas.claim_admission import AdmissionDecision
from schemas.claim_registry import ClaimRegistryRecord


def build_report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize admission independently from post-query official outcomes."""
    official = [row for row in rows if row["route_status"] in {"AUTO", "HOLD", "HUMAN_REVIEW"}]
    return {
        "total_output_claims": len(rows),
        "admission_counts": dict(sorted(Counter(row["admission_label"] for row in rows).items())),
        "admission_routed_count": sum(row["route_status"] == "ADMISSION_ROUTED" for row in rows),
        "official_route_counts": dict(sorted(Counter(row["route_status"] for row in official).items())),
        "official_verdict_counts": dict(sorted(Counter(row["verdict"] for row in official).items())),
        "official_hold_reason_counts": dict(
            sorted(Counter(row["reason_code"] for row in official if row["route_status"] == "HOLD").items())
        ),
    }


def _fill_explicit_child_numeric_slots(child: ClaimSchema) -> ClaimSchema:
    extracted = extract_explicit_numeric_slot(child.source_sentence)
    if extracted is None:
        return child
    value, unit, calculation = extracted
    updates: dict[str, object] = {}
    if child.value is None:
        updates["value"] = value
    if child.unit is None:
        updates["unit"] = unit
    if child.calculation is None:
        updates["calculation"] = calculation
    return child.model_copy(update=updates)


def _inherit_split_context(parent: ClaimSchema, child: ClaimSchema) -> ClaimSchema:
    common = ("indicator", "time", "frequency", "region", "population", "dimension", "source_hint")
    updates = {
        name: getattr(parent, name)
        for name in common
        if getattr(child, name) is None and getattr(parent, name) is not None
    }
    merged = child.model_copy(update=updates)
    if merged.parse_status != "AUTO_OK" and all(
        (merged.indicator, merged.value is not None, merged.unit, merged.time, merged.calculation)
    ):
        merged = merged.model_copy(update={"parse_status": "AUTO_OK", "parse_reason": None})
    return merged


def build_context_reparser(extractor: Any, contexts: dict[str, dict[str, Any]]):
    def context_reparser(record: ClaimRegistryRecord, claim: ClaimSchema) -> ClaimSchema:
        try:
            context = _limited_context(contexts.get(record.article_id), record.claim.source_sentence, 500)
            parsed = parse_claim(
                claim.source_sentence,
                extractor,
                article_published_at=record.article_published_at,
                article_context=context,
            )
            return _inherit_split_context(record.claim, _fill_explicit_child_numeric_slots(parsed)).model_copy(
                update={"claim_id": claim.claim_id, "source_sentence": claim.source_sentence}
            )
        except Exception:
            return claim.model_copy(
                update={"parse_status": "HOLD", "parse_reason": "CLAIM_CONTEXT_REPARSE_FAILED"}
            )

    return context_reparser


def build_child_parser(extractor: Any, contexts: dict[str, dict[str, Any]]):
    def child_parser(
        record: ClaimRegistryRecord, parent: ClaimSchema, sentence: str, child_id: str
    ) -> ClaimSchema:
        try:
            context = _limited_context(contexts.get(record.article_id), parent.source_sentence, 500)
            parsed = parse_claim(
                sentence,
                extractor,
                article_published_at=record.article_published_at,
                article_context=context,
            )
            return _inherit_split_context(parent, _fill_explicit_child_numeric_slots(parsed)).model_copy(
                update={"claim_id": child_id, "source_sentence": sentence}
            )
        except Exception:
            return parent.model_copy(
                update={
                    "claim_id": child_id,
                    "source_sentence": sentence,
                    "parse_status": "HOLD",
                    "parse_reason": "CLAIM_SPLIT_PARSE_FAILED",
                }
            )

    return child_parser


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("registry_path", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--article-context", type=Path)
    parser.add_argument("--standard", type=Path, default=Path("data/semantic_standard/concept_seed_v1.json"))
    parser.add_argument("--catalog", type=Path, default=Path("data/kosis_catalog/catalog_350.json"))
    parser.add_argument(
        "--metadata-manifest",
        type=Path,
        action="append",
        default=[Path("data/kosis_snapshots/gold_standard_v1_metadata_manifest.json")],
    )
    parser.add_argument("--as-of-metadata", type=Path, action="append", default=[])
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--live-budget-seconds", type=float, default=45.0)
    args = parser.parse_args()

    settings = Settings()
    if not settings.kosis_api_key:
        parser.error("KOSIS_API_KEY is required")
    registry = load_claim_registry(args.registry_path)
    records = registry.records[args.start:] if args.limit is None else registry.records[args.start : args.start + args.limit]
    contexts = _load_contexts(args.article_context) if args.article_context else {}
    service = build_official_evidence_service(
        OfficialEnginePaths(args.standard, args.catalog, args.as_of_metadata, args.metadata_manifest),
        kosis_api_key=settings.kosis_api_key,
        live_time_budget_seconds=args.live_budget_seconds,
    )
    extractor = create_claim_extractor(settings)
    admission_model = OpenAIAdmissionRouter(api_key=settings.openai_api_key, model=settings.openai_model)

    def contextual_admission_router(
        record: ClaimRegistryRecord, claim: ClaimSchema
    ) -> AdmissionDecision:
        try:
            return admission_model.route(
                claim,
                article_context=_limited_context(
                    contexts.get(record.article_id), claim.source_sentence, 500
                ),
            )
        except OpenAIClaimExtractorError:
            return AdmissionDecision(
                label="CONTEXT_REQUIRED",
                reason_code="ADMISSION_CLASSIFIER_UNAVAILABLE",
            )

    rows = run_claim_admission_e2e_batch(
        records,
        service,
        context_reparser=build_context_reparser(extractor, contexts) if contexts else None,
        child_parser=build_child_parser(extractor, contexts),
        contextual_admission_router=contextual_admission_router,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "admission_e2e_results.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    report = {
        "input_registry_records": len(records),
        "registry_load_errors": [error.__dict__ for error in registry.errors],
        "context_records_available": len(contexts),
        "context_policy": "title + target sentence neighborhood only (500 chars before/after)",
        **build_report(rows),
    }
    (args.output_dir / "coverage_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"output_dir": str(args.output_dir), **report}, ensure_ascii=False))


def _load_contexts(path: Path) -> dict[str, dict[str, Any]]:
    return {
        row["article_id"]
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
        for row in [json.loads(line)]
        if isinstance(row.get("title"), str) and isinstance(row.get("body"), str)
    }


if __name__ == "__main__":
    main()