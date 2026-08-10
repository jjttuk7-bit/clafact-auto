"""Derive a bounded, read-only Claim Registry pilot from source sentences."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

from core.claim_parser import StructuredClaimExtractor, parse_claim
from core.data_loader import load_standard_concepts
from core.semantic_normalizer import normalize_concept
from schemas.claim import ClaimSchema
from schemas.claim_registry import ClaimRegistryRecord
from schemas.concept import StandardConceptSchema


@dataclass(frozen=True)
class ControlledPilotResult:
    """Derived records, deterministic concepts, and auditable outcome counts."""

    records: list[ClaimRegistryRecord]
    concepts: Mapping[tuple[str, str], StandardConceptSchema]
    reason_counts: Mapping[str, int]


def derive_controlled_pilot(
    records: Iterable[ClaimRegistryRecord],
    extractor: StructuredClaimExtractor,
    standard_path: Path,
    *,
    limit: int = 50,
) -> ControlledPilotResult:
    """Re-extract at most ``limit`` records without mutating the source registry."""
    if limit < 1:
        raise ValueError("PILOT_LIMIT_MUST_BE_POSITIVE")

    standard_concepts = load_standard_concepts(standard_path)
    derived: list[ClaimRegistryRecord] = []
    concept_sidecar: dict[tuple[str, str], StandardConceptSchema] = {}
    reasons: Counter[str] = Counter()
    for record in list(records)[:limit]:
        claim = _derive_claim(record.claim.source_sentence, extractor)
        if claim.parse_status != "AUTO_OK":
            reasons[claim.parse_reason or "CLAIM_NOT_AUTO_OK"] += 1
        concept = normalize_concept(claim, standard_concepts)
        if concept.status != "MATCHED":
            reasons["CONCEPT_UNRESOLVED"] += 1
        key = (record.article_id, record.sentence_id)
        concept_sidecar[key] = concept
        derived.append(record.model_copy(update={"claim": claim, "review_status": "UNREVIEWED"}))
    return ControlledPilotResult(derived, concept_sidecar, dict(sorted(reasons.items())))


def _derive_claim(source_sentence: str, extractor: StructuredClaimExtractor) -> ClaimSchema:
    try:
        return parse_claim(source_sentence, extractor)
    except Exception:
        return ClaimSchema(
            claim_id="pilot:extraction-failed",
            source_sentence=source_sentence,
            parse_status="HOLD",
            parse_reason="EXTRACTION_FAILED",
        )


@dataclass(frozen=True)
class PilotArtifactPaths:
    """Paths written for one derived pilot execution."""

    registry_path: Path
    concepts_path: Path
    report_path: Path


def write_pilot_artifacts(
    result: ControlledPilotResult,
    source_path: Path,
    output_dir: Path,
) -> PilotArtifactPaths:
    """Write derived artifacts only outside the immutable source directory."""
    source_directory = source_path.resolve().parent
    output_directory = output_dir.resolve()
    try:
        output_directory.relative_to(source_directory)
    except ValueError:
        pass
    else:
        raise ValueError("PILOT_OUTPUT_MUST_NOT_OVERLAP_SOURCE")

    output_directory.mkdir(parents=True, exist_ok=True)
    registry_path = output_directory / "derived_registry.jsonl"
    concepts_path = output_directory / "concepts.json"
    report_path = output_directory / "extraction_report.json"
    registry_path.write_text(
        "".join(record.model_dump_json() + "\n" for record in result.records),
        encoding="utf-8",
    )
    concepts_payload = [
        {
            "article_id": article_id,
            "sentence_id": sentence_id,
            "concept": concept.model_dump(mode="json"),
        }
        for (article_id, sentence_id), concept in sorted(result.concepts.items())
    ]
    import json

    concepts_path.write_text(
        json.dumps(concepts_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    report_path.write_text(
        json.dumps(
            {"selected_records": len(result.records), "reason_counts": result.reason_counts},
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return PilotArtifactPaths(registry_path, concepts_path, report_path)