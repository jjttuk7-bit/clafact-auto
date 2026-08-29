"""Candidate-aware normalization for Claim dimension vocabulary."""

from __future__ import annotations

import re

from core.claim_dimensions import normalized_dimension_members
from schemas.candidate import KosisCandidateSchema
from schemas.claim import ClaimSchema


_COMBINED_INDUSTRY = "* 도소매·숙박음식점업(GI)"


def normalize_claim_for_candidate(
    claim: ClaimSchema, candidate: KosisCandidateSchema
) -> ClaimSchema:
    """Translate news wording only when official metadata confirms the target member."""
    source_dimensions = normalized_dimension_members(claim.dimension)
    birth_context = _is_birth_count_table_context(claim, candidate)
    dimensions: dict[str, str] = {}
    for key, values in source_dimensions.items():
        for value in values:
            if birth_context and _is_birth_descriptor(key, value, claim.time):
                continue
            normalized_key = "상태" if key.casefold() == "status" else key
            normalized_key, normalized_value = _dimension_alias(normalized_key, value, candidate)
            existing = dimensions.get(normalized_key)
            if existing is None or existing == normalized_value:
                dimensions[normalized_key] = normalized_value
            else:
                dimensions[key] = normalized_value

    population = claim.population
    if population:
        if birth_context and _is_matching_birth_year(population, claim.time):
            population = None
        else:
            population = _population_without_indicator(population, claim.indicator)
    if population:
        _, population = _dimension_alias("age", population, candidate)
    dimension_update = dimensions or claim.dimension
    if birth_context and source_dimensions:
        dimension_update = dimensions or None
    return claim.model_copy(
        update={"dimension": dimension_update, "population": population}
    )


def _dimension_alias(
    key: str, value: str, candidate: KosisCandidateSchema
) -> tuple[str, str]:
    compact = _compact(value)
    members = [
        member for values in candidate.dimension_members.values() for member in values
    ]

    if (
        candidate.tbl_id == "DT_1DA7E06S_NEW"
        and "도소매" in compact
        and "숙박" in compact
        and "음식점" in compact
    ):
        return key, _COMBINED_INDUSTRY

    if _is_education_key(key):
        if compact == "대졸":
            official = _available_member(members, "대졸이상", "대학교졸이상")
            return "교육정도", official or value
        if "고등학교" in compact and "졸업" in compact:
            return "교육정도", _available_member(members, "고졸") or value
        if ("4년제" in compact or "대학" in compact) and "이상" in compact:
            official = _available_member(members, "대졸이상", "대학교졸이상")
            return "교육정도", official or value
        if "전문대" in compact and "졸" in compact:
            return "교육정도", _available_member(members, "전문대졸") or value

    if _is_age_key(key):
        if "청년" in compact:
            official = _available_member(members, "1529세")
            if official:
                return "연령", official
        decade = re.fullmatch(r"([1-8])0대", compact)
        if decade:
            start = int(decade.group(1)) * 10
            expected = _compact(f"{start}-{start + 9}세")
            official = next((member for member in members if _compact(member) == expected), None)
            if official:
                return key, official
        if compact == "80대" and candidate.tbl_id == "DT_1B80A13":
            return key, "80 - 84세"

        if compact.endswith("인구"):
            expected = compact.removesuffix("인구")
            official = next(
                (member for member in members if _compact(member) == expected),
                None,
            )
            if official:
                return key, official

    if any("종사상지위" in name for name in candidate.dimension_names):
        status = _employment_status(compact)
        if status:
            official = next((member for member in members if status in _compact(member)), None)
            if official:
                return "종사상지위", official

    return key, value


def _employment_status(compact: str) -> str | None:
    if compact in {"임시직", "1개월이상1년미만"}:
        return "임시근로자"
    if compact in {"일용직", "1개월미만"}:
        return "일용근로자"
    if compact in {"상용직", "1년이상"}:
        return "상용근로자"
    return None


def _available_member(members: list[str], *aliases: str) -> str | None:
    return next((member for alias in aliases for member in members if _compact(member) == alias), None)


def _is_education_key(key: str) -> bool:
    return any(term in _compact(key) for term in ("학력", "교육정도"))


def _is_age_key(key: str) -> bool:
    return _compact(key) in {"age", "age_group", "연령", "연령대", "연령집단", "연령계층", "나이"}



def _population_without_indicator(population: str, indicator: str | None) -> str:
    compact_population = _compact(population)
    original_compact = compact_population
    compact_indicator = _compact(indicator or "")
    indicator_labels = {compact_indicator}
    if compact_indicator.endswith("수"):
        indicator_labels.add(compact_indicator.removesuffix("수"))
    for label in sorted((value for value in indicator_labels if value), key=len, reverse=True):
        if compact_population.endswith(label):
            compact_population = compact_population.removesuffix(label)
            break
    if compact_population.endswith("전체") and re.search(r"\d+세이상전체$", compact_population):
        compact_population = compact_population.removesuffix("전체")
    if compact_population == original_compact:
        return population
    return compact_population or population


def _is_birth_count_table_context(claim: ClaimSchema, candidate: KosisCandidateSchema) -> bool:
    return candidate.tbl_id == "DT_1B8000G" and "출생아" in _compact(claim.indicator or "")


def _is_birth_descriptor(key: str, value: str, claim_time: str | None) -> bool:
    normalized_key = _compact(key)
    if normalized_key == "세대":
        return True
    return normalized_key in {"출생연도", "출생년도"} and _is_matching_birth_year(value, claim_time)


def _is_matching_birth_year(value: str, claim_time: str | None) -> bool:
    value_match = re.fullmatch(r"\s*(\d{4})\s*년?생\s*", value)
    time_match = re.search(r"(?<!\d)(\d{4})(?!\d)", claim_time or "")
    return bool(value_match and time_match and value_match.group(1) == time_match.group(1))

def _compact(value: str) -> str:
    return re.sub(r"[\s~\-]", "", value)
