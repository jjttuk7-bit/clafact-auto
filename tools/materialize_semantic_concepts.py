"""Write deterministic Claim-to-Concept input for a reproducible E2E batch."""

from __future__ import annotations

from pathlib import Path
import sys

from core.claim_registry_loader import load_claim_registry
from core.data_loader import load_standard_concepts
from core.semantic_concept_sidecar import build_concept_sidecar, write_concept_sidecar


def run(registry_path: Path, standard_path: Path, output_path: Path) -> Path:
    registry = load_claim_registry(registry_path)
    rows = build_concept_sidecar(registry.records, load_standard_concepts(standard_path))
    return write_concept_sidecar(rows, output_path)


if __name__ == "__main__":
    run(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]))
