"""Profile-free batch execution over the shared dynamic KOSIS engine."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import date
from pathlib import Path
from typing import Any

from core.catalog_discovery import discover_catalog_candidates
from core.catalog_metadata_refresh import refresh_item_metadata
from core.catalog_search import search_semantic_catalog
from core.data_loader import SemanticStandardRecord
from core.dynamic_kosis_verifier import verify_claim_against_kosis
from core.kosis_fetcher import OfficialValueFetcher
from core.kosis_live_catalog import KosisLiveCatalogSearch
from core.kosis_openapi_transport import get_meta
from core.pipeline_trace import PipelineTrace
from core.semantic_normalizer import normalize_concept
from schemas.candidate import KosisCandidateSchema
from schemas.claim import ClaimSchema
from schemas.claim_registry import ClaimRegistryRecord
from schemas.evidence import EvidenceCellSchema


def run_dynamic_e2e_batch(
    records: Iterable[ClaimRegistryRecord],
    standard_concepts: Iterable[SemanticStandardRecord],
    catalog: Iterable[KosisCandidateSchema],
    *,
    snapshot_paths: Iterable[Path] = (),
    api_lookup: Callable[[EvidenceCellSchema], list[dict[str, Any]]] | None = None,
    kosis_api_key: str | None = None,
    live_search: KosisLiveCatalogSearch | None = None,
    claim_reparser: Callable[[ClaimSchema, date], ClaimSchema] | None = None,
) -> list[dict[str, Any]]:
    """Run structured Claims through shared mapping, KOSIS discovery, and verdict stages.

    No verification profile is accepted or consulted. KOSIS ITM metadata is cached per
    official table so a batch never repeats the same metadata request for every Claim.
    """
    catalog_rows = list(catalog)
    standard_rows = list(standard_concepts)
    value_cache: dict[str, list[dict[str, Any]]] = {}

    def cached_api_lookup(cell: EvidenceCellSchema) -> list[dict[str, Any]]:
        if api_lookup is None:
            return []
        if cell.canonical_key not in value_cache:
            value_cache[cell.canonical_key] = api_lookup(cell)
        return value_cache[cell.canonical_key]

    fetcher = OfficialValueFetcher(
        snapshot_paths,
        api_lookup=cached_api_lookup if api_lookup is not None else None,
        prefer_api=api_lookup is not None,
    )
    metadata_cache: dict[tuple[str, str], list[dict[str, object]]] = {}
    live_candidate_cache: dict[str, list[KosisCandidateSchema]] = {}
    def cached_metadata_fetcher(
        _api_key: str, org_id: str, table_id: str, **kwargs: Any
    ) -> list[dict[str, object]]:
        cache_key = (org_id, table_id)
        if cache_key not in metadata_cache:
            try:
                metadata_cache[cache_key] = list(get_meta(_api_key, org_id, table_id, **kwargs))
            except RuntimeError:
                metadata_cache[cache_key] = []
        return metadata_cache[cache_key]

    def early_hold(base: dict[str, Any], stage: str, reason_code: str) -> dict[str, Any]:
        trace = PipelineTrace.for_claim(
            base["claim_id"], preprocess_version="1.0", claim_schema_version="1.0"
        ).hold(stage, reason_code)  # type: ignore[arg-type]
        return {
            **base, "route_status": "HOLD", "reason_code": reason_code,
            "execution_trace": trace.model_dump(mode="json"),
            "versions": {
                "dataset_version": "unversioned", "preprocess_version": trace.preprocess_version,
                "claim_schema_version": trace.claim_schema_version,
                "semantic_standard_version": trace.semantic_standard_version,
                "kosis_catalog_version": trace.kosis_catalog_version,
                "matching_version": trace.matching_version, "calculation_version": trace.calculation_version,
            },
        }
    results: list[dict[str, Any]] = []
    for record in records:
        claim = record.claim
        if claim.parse_status != "AUTO_OK" and claim_reparser is not None and record.article_published_at is not None:
            try:
                reparsed = claim_reparser(claim, record.article_published_at)
                claim = reparsed.model_copy(update={"claim_id": claim.claim_id, "source_sentence": claim.source_sentence})
            except Exception:
                claim = claim.model_copy(update={"parse_status": "HOLD", "parse_reason": "CLAIM_REPARSE_FAILED"})
        base = {
            "article_id": record.article_id,
            "sentence_id": record.sentence_id,
            "claim_id": claim.claim_id,
            "profile_id": None,
            "official_value": None,
            "snapshot_hash": "",
            "versions": {},
        }
        if claim.parse_status != "AUTO_OK":
            results.append(early_hold(base, "CLAIM_PARSE", claim.parse_reason or "CLAIM_PARSE_UNCERTAIN"))
            continue
        if record.article_published_at is None:
            results.append(early_hold(base, "OFFICIAL_VALUE_FETCH", "ARTICLE_DATE_REQUIRED"))
            continue
        concept = normalize_concept(claim, standard_rows)
        if concept.status != "MATCHED":
            results.append(early_hold(base, "SEMANTIC_MAPPING", "CONCEPT_NOT_FOUND"))
            continue
        local_candidates = search_semantic_catalog(claim, concept, catalog_rows)
        if local_candidates or live_search is None:
            candidates = local_candidates
        else:
            search_query = claim.indicator or concept.canonical_name or concept.matched_alias
            if search_query not in live_candidate_cache:
                live_candidate_cache[search_query] = discover_catalog_candidates(
                    claim, concept, local_candidates, live_search
                )
            candidates = live_candidate_cache[search_query]
        candidates = refresh_item_metadata(
            candidates,
            kosis_api_key,
            metadata_fetcher=cached_metadata_fetcher,
        )
        verdict = verify_claim_against_kosis(
            claim, concept, candidates, article_date=record.article_published_at, official_fetcher=fetcher
        )
        results.append({
            **base,
            "route_status": verdict.route_status,
            "reason_code": verdict.reason_code,
            "verdict": verdict.verdict,
            "official_value": verdict.evidence_values[0] if verdict.evidence_values else None,
            "calculated_value": verdict.calculated_value,
            "evidence_values": verdict.evidence_values,
            "evidence_cells": [cell.model_dump(mode="json") for cell in verdict.evidence_cells],
            "execution_trace": verdict.execution_trace.model_dump(mode="json") if verdict.execution_trace else None,
            "versions": {
                "dataset_version": verdict.dataset_version,
                "preprocess_version": verdict.preprocess_version,
                "claim_schema_version": verdict.claim_schema_version,
                "semantic_standard_version": verdict.semantic_standard_version,
                "kosis_catalog_version": verdict.kosis_catalog_version,
                "matching_version": verdict.matching_version,
                "calculation_version": verdict.calculation_version,
            },
        })
    return results
