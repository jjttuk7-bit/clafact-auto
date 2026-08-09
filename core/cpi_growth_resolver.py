"""Resolve only registered detailed CPI claims into two official index cells."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from schemas.claim import ClaimSchema
from schemas.evidence import CalculationPlan, EvidenceCellSchema

_PROFILE_PATH = Path(__file__).resolve().parents[1] / "data" / "semantic_standard" / "cpi_detail_growth_profiles.json"


@dataclass(frozen=True, slots=True)
class CpiGrowthPlan:
    """A deterministic two-cell plan for a registered CPI item."""

    calculation_plan: CalculationPlan
    dataset_version: str


def resolve_cpi_growth_plan(claim: ClaimSchema) -> CpiGrowthPlan | None:
    """Return a plan only for an exact registered monthly year-on-year CPI detail claim."""
    if claim.parse_status != "AUTO_OK" or claim.calculation != "GROWTH_RATE" or claim.unit != "%":
        return None
    period = _month_key(claim.time)
    profile = _profile_for_indicator(claim.indicator)
    if period is None or profile is None:
        return None
    current_period = f"{period[0]:04d}{period[1]:02d}"
    prior_period = f"{period[0] - 1:04d}{period[1]:02d}"
    cells = [
        _cell(profile, current_period),
        _cell(profile, prior_period),
    ]
    return CpiGrowthPlan(
        calculation_plan=CalculationPlan(calculation_type="GROWTH_RATE", required_cells=cells),
        dataset_version=_dataset_version(),
    )


def _cell(profile: dict[str, object], period: str) -> EvidenceCellSchema:
    codes = dict(profile["dimension_codes"])  # type: ignore[arg-type]
    key = "|".join([str(profile["tbl_id"]), str(profile["itm_id"]), period, *(f"{name}:{value}" for name, value in codes.items())])
    return EvidenceCellSchema(
        org_id=str(profile["org_id"]),
        tbl_id=str(profile["tbl_id"]),
        itm_id=str(profile["itm_id"]),
        dimension_codes=codes,
        prd_se="M",
        prd_de=period,
        unit="2020=100",
        canonical_key=key,
        status="CONFIRMED",
    )


def _profile_for_indicator(indicator: str | None) -> dict[str, object] | None:
    """Resolve approved news-label suffixes without fuzzy item matching."""
    normalized = _normalize(indicator)
    profiles = _profiles()
    if normalized in profiles:
        return profiles[normalized]
    for suffix in ("소비자물가지수", "소비자물가", "물가지수", "물가", "가격"):
        if normalized.endswith(suffix):
            return profiles.get(normalized.removesuffix(suffix))
    return None


@lru_cache(maxsize=1)
def _profiles() -> dict[str, dict[str, object]]:
    payload = json.loads(_PROFILE_PATH.read_text(encoding="utf-8"))
    rows = payload.get("profiles", [])
    return {
        _normalize(str(row["indicator"])): row
        for row in rows
        if isinstance(row, dict) and all(key in row for key in ("indicator", "org_id", "tbl_id", "itm_id", "dimension_codes"))
    }


@lru_cache(maxsize=1)
def _dataset_version() -> str:
    payload = json.loads(_PROFILE_PATH.read_text(encoding="utf-8"))
    return str(payload.get("dataset_version", "unversioned"))


def _month_key(value: str | None) -> tuple[int, int] | None:
    if not value:
        return None
    match = re.search(r"(?P<year>\d{4})\s*년\s*(?P<month>\d{1,2})\s*월", value)
    if match is None:
        return None
    return int(match.group("year")), int(match.group("month"))


def _normalize(value: str | None) -> str:
    return "".join((value or "").split()).casefold()
