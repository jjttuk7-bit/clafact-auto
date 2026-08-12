"""Structural compatibility checks that run before semantic scoring."""

from __future__ import annotations

import re

from schemas.candidate import HardGuardResult, KosisCandidateSchema
from schemas.claim import ClaimSchema
from core.claim_dimensions import dimension_member_values
from core.unit_normalizer import compatible_units


def apply_hard_guard(claim: ClaimSchema, candidate: KosisCandidateSchema) -> HardGuardResult:
    """Reject candidates with non-negotiable slot conflicts."""
    reject_codes: list[str] = []
    if candidate.metadata_status in {
        "LIVE_SEARCH_UNRESOLVED",
        "OFFICIAL_ITEM_METADATA_UNAVAILABLE",
    } or (
        claim.frequency
        and candidate.metadata_status == "OFFICIAL_ITEM_METADATA_READY"
        and not candidate.frequency
    ):
        reject_codes.append("METADATA_INCOMPLETE")
    if _frequency_conflict(claim, candidate):
        reject_codes.append("FREQUENCY_CONFLICT")
    if _unit_conflict(claim, candidate):
        reject_codes.append("UNIT_CONFLICT")
    if _age_dimension_required(claim, candidate):
        reject_codes.append("AGE_DIMENSION_REQUIRED")
    if _sex_dimension_required(claim, candidate):
        reject_codes.append("SEX_DIMENSION_REQUIRED")
    if _region_conflict(claim, candidate):
        reject_codes.append("REGION_GRANULARITY_CONFLICT")
    if _dimension_member_conflict(claim, candidate):
        reject_codes.append("DIMENSION_MEMBER_CONFLICT")
    if _time_not_available(claim, candidate):
        reject_codes.append("TIME_NOT_AVAILABLE")
    if _forecast_claim(claim):
        reject_codes.append("FORECAST_CLAIM")
    return HardGuardResult(passed=not reject_codes, reject_codes=reject_codes)


def _frequency_conflict(claim: ClaimSchema, candidate: KosisCandidateSchema) -> bool:
    return bool(claim.frequency and candidate.frequency and _key(claim.frequency) not in {_key(item) for item in candidate.frequency.split("|")})


def _unit_conflict(claim: ClaimSchema, candidate: KosisCandidateSchema) -> bool:
    if claim.calculation == "DIFFERENCE" and _key(claim.unit or "") in {"%p", "%포인트", "퍼센트포인트"}:
        return not any(_key(unit) in {"%", "퍼센트"} for unit in candidate.unit_names)
    if claim.calculation in {"GROWTH_RATE", "SHARE", "RATIO", "MULTIPLE"}:
        return False
    return bool(claim.unit and candidate.unit_names and not any(compatible_units(claim.unit, unit) for unit in candidate.unit_names))


def _age_dimension_required(claim: ClaimSchema, candidate: KosisCandidateSchema) -> bool:
    return bool(claim.population and "세" in claim.population and not _has_dimension(candidate, "연령"))


def _sex_dimension_required(claim: ClaimSchema, candidate: KosisCandidateSchema) -> bool:
    return bool(claim.dimension and "sex" in claim.dimension and not _has_dimension(candidate, "성별"))


def _region_conflict(claim: ClaimSchema, candidate: KosisCandidateSchema) -> bool:
    if not claim.region or claim.region in {"전국", "대한민국", "한국"}:
        return False
    return not any(_has_dimension(candidate, token) for token in ("시도", "지역", "행정", "읍면"))


def _dimension_member_conflict(claim: ClaimSchema, candidate: KosisCandidateSchema) -> bool:
    if not claim.dimension or not candidate.dimension_members:
        return False
    official_members = {_key(member) for members in candidate.dimension_members.values() for member in members}
    table_scope = _key(candidate.tbl_name)
    return any(
        (member := _key(value)) not in official_members and member not in table_scope
        for value in dimension_member_values(claim.dimension)
    )


def _time_not_available(claim: ClaimSchema, candidate: KosisCandidateSchema) -> bool:
    if not claim.time or not candidate.start_period or not candidate.end_period:
        return False
    match = re.search(r"\d{4}", claim.time)
    if not match:
        return False
    try:
        year = int(match.group())
        return year < int(candidate.start_period[:4]) or year > int(candidate.end_period[:4])
    except ValueError:
        return False


def _forecast_claim(claim: ClaimSchema) -> bool:
    return any(token in claim.source_sentence for token in ("전망", "예측", "예상"))


def _has_dimension(candidate: KosisCandidateSchema, token: str) -> bool:
    return any(token in name for name in candidate.dimension_names)


def _key(value: str) -> str:
    normalized = re.sub(r"\s+", "", value).casefold(); return {"monthly":"월", "month":"월", "m":"월", "yearly":"년", "year":"년", "annual":"년", "y":"년", "연":"년"}.get(normalized, normalized)
