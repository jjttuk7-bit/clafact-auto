"""Profile-free batch execution over the shared dynamic KOSIS engine."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from pathlib import Path
from typing import Any

from core.catalog_metadata_refresh import refresh_item_metadata
from core.catalog_search import search_semantic_catalog
from core.dynamic_kosis_verifier import verify_claim_against_kosis
from core.kosis_fetcher import OfficialValueFetcher
from schemas.candidate import KosisCandidateSchema
from schemas.claim_registry import ClaimRegistryRecord
from schemas.concept import StandardConceptSchema
from schemas.evidence import EvidenceCellSchema


def run_dynamic_e2e_batch(
    records: Iterable[ClaimRegistryRecord],
    concepts: Mapping[tuple[str, str], StandardConceptSchema],
    catalog: Iterable[KosisCandidateSchema],
    *,
    snapshot_paths: Iterable[Path] = (),
    api_lookup: Callable[[EvidenceCellSchema], list[dict[str, Any]]] | None = None,
    kosis_api_key: str | None = None,
) -> list[dict[str, Any]]:
    """Run each structured Claim through catalog, coordinates, fetch, calculation, verdict.

    No verification profile is accepted or consulted.
    """
    catalog_rows = list(catalog)
    fetcher = OfficialValueFetcher(snapshot_paths, api_lookup=api_lookup, prefer_api=api_lookup is not None)
    results: list[dict[str, Any]] = []
    for record in records:
        claim = record.claim
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
            results.append({**base, "route_status": "HOLD", "reason_code": claim.parse_reason or "CLAIM_PARSE_UNCERTAIN"})
            continue
        if record.article_published_at is None:
            results.append({**base, "route_status": "HOLD", "reason_code": "ARTICLE_DATE_REQUIRED"})
            continue
        concept = concepts.get((record.article_id, record.sentence_id))
        if concept is None or concept.status != "MATCHED":
            results.append({**base, "route_status": "HOLD", "reason_code": "CONCEPT_NOT_FOUND"})
            continue
        candidates = search_semantic_catalog(claim, concept, catalog_rows)
        candidates = refresh_item_metadata(candidates, kosis_api_key)
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
