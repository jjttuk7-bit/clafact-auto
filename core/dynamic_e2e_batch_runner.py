"""Batch execution over the shared dynamic KOSIS engine."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from typing import Any

from core.catalog_discovery import build_catalog_discovery_queries, discover_catalog_candidates
from core.catalog_metadata_refresh import refresh_item_metadata
from core.catalog_search import search_semantic_catalog
from core.claim_contract import assess_claim_contract
from core.claim_slot_quality import assess_claim_slot_quality
from core.claim_parse_reason import operational_parse_reason
from core.deterministic_slot_enricher import apply_explicit_slots
from core.hard_guard import apply_hard_guard
from core.data_loader import SemanticStandardRecord
from core.dynamic_kosis_verifier import verify_claim_against_kosis
from core.export_claim_scope import classify_export_claim_scope
from core.kosis_fetcher import OfficialValueFetcher
from core.kosis_live_catalog import KosisLiveCatalogSearch
from core.kosis_discovery_snapshot import DiscoverySnapshot, SnapshotCatalogSearch, SnapshotValueLookup
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
    discovery_snapshot: DiscoverySnapshot | None = None,
    refresh_discovery_snapshot: bool = False,
    claim_reparser: Callable[[ClaimSchema, date], ClaimSchema] | None = None,
    reparse_workers: int = 1,
) -> list[dict[str, Any]]:
    """Run structured Claims through shared mapping, KOSIS discovery, and verdict stages.

    KOSIS ITM metadata is cached per
    official table so a batch never repeats the same metadata request for every Claim.
    """
    materialized_records = list(records)
    if claim_reparser is not None and reparse_workers > 1:
        def reparse_record(record: ClaimRegistryRecord) -> ClaimRegistryRecord:
            claim = record.claim
            if claim.parse_status == "AUTO_OK" or record.article_published_at is None:
                return record
            try:
                reparsed = claim_reparser(claim, record.article_published_at)
                normalized = reparsed.model_copy(update={"claim_id": claim.claim_id, "source_sentence": claim.source_sentence})
            except Exception:
                normalized = claim.model_copy(update={"parse_status": "HOLD", "parse_reason": "CLAIM_REPARSE_FAILED"})
            return record.model_copy(update={"claim": normalized})

        with ThreadPoolExecutor(max_workers=reparse_workers) as executor:
            materialized_records = list(executor.map(reparse_record, materialized_records))
        claim_reparser = None

    catalog_rows = list(catalog)
    standard_rows = list(standard_concepts)
    snapshot_search = (
        SnapshotCatalogSearch(discovery_snapshot, live_search, refresh=refresh_discovery_snapshot)
        if discovery_snapshot is not None
        else live_search
    )
    snapshot_hash = discovery_snapshot.content_hash if discovery_snapshot is not None else None
    value_cache: dict[str, list[dict[str, Any]]] = {}

    def cached_api_lookup(cell: EvidenceCellSchema) -> list[dict[str, Any]]:
        if api_lookup is None:
            return []
        if cell.canonical_key not in value_cache:
            value_cache[cell.canonical_key] = api_lookup(cell)
        return value_cache[cell.canonical_key]

    value_lookup = (
        SnapshotValueLookup(discovery_snapshot, cached_api_lookup if api_lookup is not None else None, refresh=refresh_discovery_snapshot)
        if discovery_snapshot is not None
        else (cached_api_lookup if api_lookup is not None else None)
    )
    fetcher = OfficialValueFetcher(
        snapshot_paths,
        api_lookup=value_lookup,
        prefer_api=value_lookup is not None,
    )
    metadata_cache: dict[tuple[str, str, str], list[dict[str, object]]] = {}
    live_candidate_cache: dict[tuple[str, ...], list[KosisCandidateSchema]] = {}
    def cached_metadata_fetcher(
        _api_key: str, org_id: str, table_id: str, **kwargs: Any
    ) -> list[dict[str, object]]:
        meta_type = str(kwargs.get("meta_type", "ITM")).upper()
        cache_key = (org_id, table_id, meta_type)
        if cache_key not in metadata_cache:
            frozen_metadata = (
                discovery_snapshot.metadata_for(org_id, table_id, meta_type=meta_type)
                if discovery_snapshot is not None
                else None
            )
            if frozen_metadata is not None:
                metadata_cache[cache_key] = frozen_metadata
            elif discovery_snapshot is not None and not refresh_discovery_snapshot:
                metadata_cache[cache_key] = []
            else:
                try:
                    fetched = get_meta(_api_key, org_id, table_id, **kwargs)
                    metadata_cache[cache_key] = list(fetched) if isinstance(fetched, list) else [fetched]
                    if discovery_snapshot is not None:
                        discovery_snapshot.record_metadata(
                            org_id, table_id, metadata_cache[cache_key], meta_type=meta_type
                        )
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
            "kosis_discovery_snapshot_hash": snapshot_hash,
            "versions": {
                "dataset_version": "unversioned", "preprocess_version": trace.preprocess_version,
                "claim_schema_version": trace.claim_schema_version,
                "semantic_standard_version": trace.semantic_standard_version,
                "kosis_catalog_version": trace.kosis_catalog_version,
                "matching_version": trace.matching_version, "calculation_version": trace.calculation_version,
            },
        }
    results: list[dict[str, Any]] = []
    for record in materialized_records:
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
            "source_sentence": claim.source_sentence,
            "official_value": None,
            "snapshot_hash": "",
            "versions": {},
            "kosis_discovery_snapshot_hash": snapshot_hash,
        }
        if claim.parse_status != "AUTO_OK":
            held = early_hold(
                base,
                "CLAIM_PARSE",
                operational_parse_reason(claim.parse_reason),
            )
            held["parse_reason_detail"] = claim.parse_reason
            results.append(held)
            continue
        export_scope = classify_export_claim_scope(claim, record.article_published_at)
        if export_scope.reason_code is not None:
            held = early_hold(base, "CLAIM_PARSE", export_scope.reason_code)
            held["export_scope"] = {
                "route": export_scope.route,
                "reason_code": export_scope.reason_code,
            }
            results.append(held)
            continue
        claim = apply_explicit_slots(claim)
        if claim.parse_status != "AUTO_OK":
            held = early_hold(
                base,
                "CLAIM_PARSE",
                operational_parse_reason(claim.parse_reason),
            )
            held["parse_reason_detail"] = claim.parse_reason
            results.append(held)
            continue
        slot_quality = assess_claim_slot_quality(claim)
        if slot_quality.status == "HOLD":
            held = early_hold(base, "CLAIM_PARSE", slot_quality.reason_code or "CLAIM_PARSE_UNCERTAIN")
            held["slot_quality"] = {
                "reason_code": slot_quality.reason_code,
                "detected_modifier": slot_quality.detected_modifier,
            }
            results.append(held)
            continue
        contract = assess_claim_contract(claim)
        if contract.status == "HOLD":
            held = early_hold(
                base, "CLAIM_PARSE", contract.reason_code or "CLAIM_PARSE_UNCERTAIN"
            )
            held["claim_contract"] = {
                "missing_slots": list(contract.missing_slots),
                "detail": contract.detail,
            }
            results.append(held)
            continue
        if record.article_published_at is None:
            results.append(early_hold(base, "OFFICIAL_VALUE_FETCH", "ARTICLE_DATE_REQUIRED"))
            continue
        concept = normalize_concept(claim, standard_rows)
        if concept.status != "MATCHED":
            results.append(early_hold(base, "SEMANTIC_MAPPING", "CONCEPT_NOT_FOUND"))
            continue
        local_candidates = search_semantic_catalog(claim, concept, catalog_rows)
        local_guarded = [candidate for candidate in local_candidates if apply_hard_guard(claim, candidate).passed]
        if (local_guarded and not concept.kosis_search_terms) or snapshot_search is None:
            candidates = local_candidates
        else:
            search_query = tuple(build_catalog_discovery_queries(claim, concept))
            if search_query not in live_candidate_cache:
                discovered = discover_catalog_candidates(claim, concept, [], snapshot_search)
                by_key = {(candidate.org_id, candidate.tbl_id): candidate for candidate in local_candidates}
                for candidate in discovered:
                    by_key.setdefault((candidate.org_id, candidate.tbl_id), candidate)
                live_candidate_cache[search_query] = list(by_key.values())
            candidates = live_candidate_cache[search_query]
        candidates = refresh_item_metadata(
            candidates,
            kosis_api_key,
            metadata_fetcher=cached_metadata_fetcher,
            allow_without_api_key=discovery_snapshot is not None,
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
    if discovery_snapshot is not None:
        final_snapshot_hash = discovery_snapshot.content_hash
        for result in results:
            result['kosis_discovery_snapshot_hash'] = final_snapshot_hash
    return results
