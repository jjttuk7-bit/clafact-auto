"""Apply explicit Semantic Standard to KOSIS-table bindings before matching."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from schemas.candidate import KosisCandidateSchema
from schemas.claim import ClaimSchema
from schemas.concept import StandardConceptSchema

_BINDING_PATH = Path(__file__).resolve().parents[1] / "data" / "semantic_standard" / "kosis_bindings.json"


def apply_catalog_binding(
    claim: ClaimSchema,
    concept: StandardConceptSchema,
    candidates: Iterable[KosisCandidateSchema],
) -> list[KosisCandidateSchema]:
    """Narrow candidates only when a complete, registered semantic binding applies."""
    materialized = list(candidates)
    for binding in _load_bindings():
        if not _binding_applies(binding, claim, concept):
            continue
        table_id = binding.get("tbl_id")
        bound = [candidate for candidate in materialized if candidate.tbl_id == table_id]
        if len(bound) == 1:
            return bound
    return materialized


def _load_bindings() -> list[dict[str, object]]:
    payload = json.loads(_BINDING_PATH.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, list):
        raise ValueError("KOSIS_BINDING_INVALID")
    return [row for row in payload if isinstance(row, dict)]


def _binding_applies(binding: dict[str, object], claim: ClaimSchema, concept: StandardConceptSchema) -> bool:
    return (
        binding.get("standard_key") == concept.standard_key
        and binding.get("frequency") == claim.frequency
        and binding.get("region") == claim.region
        and binding.get("population") == claim.population
    )
