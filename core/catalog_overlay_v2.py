"""Versioned KOSIS catalog overlay for recurring official-statistics domains."""

from __future__ import annotations

from pathlib import Path

from core.data_loader import load_kosis_catalog
from schemas.candidate import KosisCandidateSchema


def load_catalog_with_overlay_v2(
    base_path: Path, overlay_path: Path
) -> list[KosisCandidateSchema]:
    """Merge base and overlay by official organisation/table identity."""
    merged = {
        (candidate.org_id, candidate.tbl_id): candidate
        for candidate in load_kosis_catalog(base_path)
    }
    for candidate in load_kosis_catalog(overlay_path):
        merged[(candidate.org_id, candidate.tbl_id)] = candidate
    return sorted(merged.values(), key=lambda item: (item.tbl_id, item.org_id))
