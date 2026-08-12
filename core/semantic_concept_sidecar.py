"""Materialize deterministic per-Claim semantic mappings for reproducible batch runs."""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

from core.data_loader import SemanticStandardRecord
from core.semantic_normalizer import normalize_concept
from schemas.claim_registry import ClaimRegistryRecord


def build_concept_sidecar(
    records: Iterable[ClaimRegistryRecord],
    standards: Iterable[SemanticStandardRecord],
) -> list[dict[str, object]]:
    """Return sorted Concept mappings without mutating registry records."""
    standard_list = list(standards)
    rows = []
    for record in records:
        concept = normalize_concept(record.claim, standard_list)
        rows.append(
            {
                "article_id": record.article_id,
                "sentence_id": record.sentence_id,
                "concept": concept.model_dump(mode="json"),
            }
        )
    return sorted(rows, key=lambda row: (str(row["article_id"]), str(row["sentence_id"])))


def write_concept_sidecar(rows: list[dict[str, object]], path: Path) -> Path:
    """Persist a versionable JSON input consumed by the E2E batch runner."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
