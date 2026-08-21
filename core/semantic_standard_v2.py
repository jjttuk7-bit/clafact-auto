"""Versioned semantic overlay loader for repeated Registry failure domains."""

from __future__ import annotations

from pathlib import Path

from core.data_loader import SemanticStandardRecord, load_standard_concepts


def load_semantic_standard_v2(
    base_path: Path, overlay_path: Path
) -> list[SemanticStandardRecord]:
    """Return the immutable v1 base plus a small versioned alias/concept overlay."""
    return [
        *load_standard_concepts(base_path),
        *load_standard_concepts(overlay_path),
    ]
