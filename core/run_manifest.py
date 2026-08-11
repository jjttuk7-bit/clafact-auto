"""Build immutable metadata for reproducible CLAFACT-AUTO runs."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from typing import Mapping

_REQUIRED_RECONCILIATION = ("target_count", "structured_count", "raw_count", "selection_rule")
_REQUIRED_VERSIONS = (
    "dataset_version", "preprocess_version", "claim_schema_version",
    "semantic_standard_version", "kosis_catalog_version", "matching_version", "calculation_version",
)


def build_run_manifest(
    *, run_id: str, inputs: Mapping[str, Path], versions: Mapping[str, str],
    reconciliation: Mapping[str, object], code_revision: str,
) -> dict[str, object]:
    """Return explicit, serializable run provenance without reading secret values."""
    for field in _REQUIRED_RECONCILIATION:
        if field not in reconciliation:
            raise ValueError(f"Missing reconciliation field: {field}")
    for field in _REQUIRED_VERSIONS:
        if field not in versions:
            raise ValueError(f"Missing version field: {field}")
    if not run_id or not code_revision:
        raise ValueError("run_id and code_revision are required")
    return {
        "run_id": run_id,
        "code_revision": code_revision,
        "inputs": {
            name: {"path": str(path), "sha256": sha256(path.read_bytes()).hexdigest()}
            for name, path in sorted(inputs.items())
        },
        "versions": {name: versions[name] for name in _REQUIRED_VERSIONS},
        "reconciliation": {name: reconciliation[name] for name in _REQUIRED_RECONCILIATION},
    }
