"""Resolve a selected KOSIS table to an auditable evidence coordinate."""

from __future__ import annotations

import re

from core.claim_dimensions import dimension_member_values, normalized_dimension_members
from core.member_code_mapper import resolve_member_code
from core.unit_normalizer import compatible_units
from schemas.candidate import KosisCandidateSchema
from schemas.claim import ClaimSchema
from schemas.evidence import EvidenceCellSchema


def resolve_evidence_cell(claim: ClaimSchema, candidate: KosisCandidateSchema) -> EvidenceCellSchema:
    """Confirm an evidence cell only from catalog metadata or official coordinates."""
    dimensions, coordinate_resolved = _resolve_dimensions(claim, candidate)
    if coordinate_resolved and not _claim_coordinate_requirements_covered(
        claim,
        candidate,
        dimensions,
    ):
        coordinate_resolved = False
    indicator_terms = _indicator_terms(claim)
    matches = [
        (item_id, item_name)
        for item_id, item_name in zip(candidate.core_item_ids, candidate.core_item_names)
        if _item_matches_indicator(_normalize(item_name), indicator_terms)
    ]
    if (
        not matches
        and len(candidate.core_item_ids) == 1
        and _claim_dimensions_confirmed(claim, dimensions)
    ):
        matches = [(candidate.core_item_ids[0], candidate.core_item_names[0])]
    status = "CONFIRMED" if len(matches) == 1 and claim.time and claim.unit else "AMBIGUOUS" if len(matches) > 1 else "UNRESOLVED"
    item_id = matches[0][0] if len(matches) == 1 else "UNRESOLVED"
    if not coordinate_resolved:
        status = "UNRESOLVED"
    derived_calculation = claim.calculation in {"GROWTH_RATE", "DIFFERENCE", "SHARE", "RATIO", "MULTIPLE"}
    item_unit = candidate.item_units.get(item_id)
    unit = item_unit if item_unit and (derived_calculation or compatible_units(claim.unit or "", item_unit)) else None
    if unit is None:
        unit = next((value for value in candidate.unit_names if claim.unit and compatible_units(claim.unit, value)), None)
    if unit is None and derived_calculation:
        unit = candidate.unit_names[0] if len(candidate.unit_names) == 1 else None
    if unit is None:
        status = "UNRESOLVED"
    frequency = _resolve_frequency(claim.frequency, candidate.frequency)
    period = _period_key(claim.time)
    dimension_codes = _resolve_dimension_codes(dimensions, candidate.dimension_member_codes)
    if set(dimension_codes) != set(dimensions):
        status = "UNRESOLVED"
    obj_id, member_code = next(iter(dimensions.items()), (None, None))
    canonical_key = _key(
        candidate.org_id,
        candidate.tbl_id,
        item_id,
        obj_id,
        member_code,
        frequency,
        period,
        dimensions,
        include_dimensions=True,
    )
    return EvidenceCellSchema(
        org_id=candidate.org_id,
        tbl_id=candidate.tbl_id,
        itm_id=item_id,
        obj_id=obj_id,
        member_code=member_code,
        dimension_members=dimensions,
        dimension_codes=dimension_codes,
        prd_se=frequency,
        prd_de=period,
        unit=unit,
        canonical_key=canonical_key,
        status=status,
    )


def _resolve_dimensions(claim: ClaimSchema, candidate: KosisCandidateSchema) -> tuple[dict[str, str], bool]:
    if not candidate.dimension_ids:
        return {}, True
    selected: dict[str, str] = {}
    for index, dimension_id in enumerate(candidate.dimension_ids):
        members = candidate.dimension_members.get(dimension_id, [])
        axis_name = candidate.dimension_names[index] if index < len(candidate.dimension_names) else None
        axis = _axis_kind(axis_name)
        targets = _axis_targets(claim, axis_name)
        if len(members) == 1:
            if (
                _axis_has_explicit_claim_value(claim, axis)
                and _normalize(members[0]) not in targets
            ):
                return {}, False
            selected[dimension_id] = members[0]
            continue
        matches = [member for member in members if _normalize(member) and _normalize(member) in targets]
        total_members = [member for member in members if _is_total_member(member)]
        if len(matches) == 1:
            selected[dimension_id] = matches[0]
            continue
        if not matches and _axis_has_explicit_claim_value(claim, axis):
            return {}, False
        if not matches and len(total_members) == 1:
            selected[dimension_id] = total_members[0]
            continue
        return {}, False
    return selected, True


def _axis_targets(claim: ClaimSchema, axis_name: str | None) -> set[str]:
    """Return only Claim values applicable to one named KOSIS axis."""
    axis = _axis_kind(axis_name)
    dimensions = claim.dimension or {}
    values = dimension_member_values(dimensions)
    if axis == "region":
        region = "전국" if claim.region in {"한국", "대한민국", "전국"} else claim.region
        values = [region] if region else ["전국"]
    elif axis == "population":
        values = _dimension_values_for_axis(dimensions, "population")
        if not values and claim.population:
            values = [claim.population]
    elif axis == "age":
        values = _dimension_values_for_axis(dimensions, "age")
        if not values and claim.population:
            values = [claim.population]
    elif axis:
        values = dimension_member_values(dimensions) if set(dimensions) == {"raw"} else _dimension_values_for_axis(dimensions, axis)
    return {_normalize(value) for value in values if _normalize(value)}


def _axis_kind(axis_name: str | None) -> str | None:
    normalized = _normalize(axis_name)
    aliases = {
        "region": ("지역", "시도", "시군구", "행정구역"),
        "gender": ("성별", "남녀", "gender", "sex"),
        "age": ("연령", "나이", "age"),
        "industry": ("산업", "업종", "직종", "industry"),
        "education": ("학력", "교육정도", "교육수준", "education"),
        "product": ("품목", "상품", "재화", "product", "item"),
        "population": ("모집단", "대상", "population"),
    }
    for kind, terms in aliases.items():
        if any(_normalize(term) in normalized for term in terms):
            return kind
    return f"custom:{normalized}" if normalized else None


def _axis_has_explicit_claim_value(claim: ClaimSchema, axis: str | None) -> bool:
    dimensions = claim.dimension or {}
    if axis == "region":
        return bool(claim.region)
    if axis == "population":
        return bool(claim.population or _dimension_values_for_axis(dimensions, "population"))
    if axis == "age":
        return bool(claim.population or _dimension_values_for_axis(dimensions, "age"))
    if axis:
        return bool(_dimension_values_for_axis(dimensions, axis))
    return False

def _dimension_values_for_axis(dimensions: dict[str, str], axis: str) -> list[str]:
    named_members = normalized_dimension_members(dimensions)
    if axis.startswith("custom:"):
        axis_label = axis.removeprefix("custom:")
        return [
            value
            for key, values in named_members.items()
            if (key_label := _normalize(key)) and (key_label in axis_label or axis_label in key_label)
            for value in values
        ]
    return [
        value
        for key, values in named_members.items()
        if _axis_kind(key) == axis
        for value in values
    ]


def _dimension_text(value: dict[str, str] | None) -> str | None:
    """Flatten the structured 12-slot dimension into deterministic search text."""
    if not value:
        return None
    return " ".join(dimension_member_values(value))


def _claim_coordinate_requirements_covered(
    claim: ClaimSchema,
    candidate: KosisCandidateSchema,
    dimensions: dict[str, str],
) -> bool:
    required = {
        _normalize(value)
        for key, values in normalized_dimension_members(claim.dimension).items()
        for value in values
        if _normalize(value) and not _is_methodology_qualifier(claim, key, value)
    }
    population = _normalize(claim.population)
    has_age_dimension = any(
        _axis_kind(key) == "age"
        for key in normalized_dimension_members(claim.dimension)
    )
    if (
        population
        and not has_age_dimension
        and (re.search(r"\d+(?:대|세)", population) or population in {"청년층", "고령층"})
    ):
        required.add(population)
    region = _normalize(claim.region)
    if region and region != "전국":
        required.add(region)
    if not required:
        return True
    available = {_normalize(value) for value in dimensions.values() if _normalize(value)}
    available.update(_normalize(value) for value in candidate.core_item_names if _normalize(value))
    available.update(
        _normalize(value)
        for value in candidate.binding_scope_terms
        if _normalize(value)
    )
    available.add(_normalize(candidate.tbl_name))
    return all(
        any(target == value or target in value or (_is_total_member(target) and _is_total_member(value)) for value in available)
        for target in required
    )

def _is_methodology_qualifier(claim: ClaimSchema, key: str, value: str) -> bool:
    """Do not require an age methodology label as a KOSIS coordinate member."""
    normalized_key = _normalize(key)
    normalized_value = _normalize(value)
    return bool(
        claim.population
        and "세" in claim.population
        and normalized_key in {"기준", "비교기준"}
        and normalized_value.startswith("국제비교")
    )


def _claim_dimensions_confirmed(claim: ClaimSchema, dimensions: dict[str, str]) -> bool:
    requested = {_normalize(value) for value in dimension_member_values(claim.dimension) if _normalize(value)}
    selected = {_normalize(value) for value in dimensions.values() if _normalize(value)}
    return bool(requested) and requested.issubset(selected)

def _is_total_member(member: str) -> bool:
    normalized = _normalize(member)
    return normalized in {"계", "전체", "합계", "전국", "대한민국", "한국"} or normalized.endswith("계")


def _resolve_frequency(claim_frequency: str | None, candidate_frequency: str | None) -> str:
    """Use the normalized Claim frequency when a multi-frequency table supports it."""
    normalized_claim = _frequency_label(claim_frequency)
    if normalized_claim and candidate_frequency:
        available = {_frequency_label(part) for part in candidate_frequency.split("|")}
        if normalized_claim in available:
            return normalized_claim if "|" in candidate_frequency else claim_frequency
    return _frequency_label(candidate_frequency) or normalized_claim or "UNRESOLVED"


def _frequency_label(value: str | None) -> str | None:
    normalized = (value or "").strip().casefold()
    return {
        "y": "년", "year": "년", "yearly": "년", "annual": "년", "연": "년", "연간": "년", "년": "년",
        "m": "월", "month": "월", "monthly": "월", "월": "월",
        "q": "분기", "quarter": "분기", "quarterly": "분기", "분기": "분기",
    }.get(normalized, (value or "").strip() or None)

def _period_key(value: str | None) -> str:
    if not value:
        return "UNRESOLVED"
    match = re.search(r"(?P<year>\d{4})\s*년?\s*(?P<month>\d{1,2})\s*월", value)
    if match:
        return f"{match.group('year')}-{int(match.group('month')):02d}"
    quarter = re.search(
        r"(?P<year>\d{4})\s*년?\s*(?P<quarter>[1-4])\s*분기",
        value,
    )
    if quarter:
        return f"{quarter.group('year')}-Q{quarter.group('quarter')}"
    return value.replace("년", "").strip()


def _resolve_dimension_codes(
    dimensions: dict[str, str],
    candidate_codes: dict[str, dict[str, str]],
) -> dict[str, str]:
    return {
        dimension_id: code
        for dimension_id, member_name in dimensions.items()
        if (code := resolve_member_code(candidate_codes, dimension_id, member_name)) is not None
    }


def _normalize(value: str | None) -> str:
    normalized = (value or "").replace(" ", "").replace("-", "").replace("~", "")
    return (normalized.replace("서울특별시", "서울").replace("부산광역시", "부산")
        .replace("대구광역시", "대구").replace("인천광역시", "인천")
        .replace("광주광역시", "광주").replace("대전광역시", "대전")
        .replace("울산광역시", "울산").replace("여성", "여자")
        .replace("강원특별자치도", "강원").replace("강원도", "강원")
        .replace("충청북도", "충북").replace("충청남도", "충남")
        .replace("전북특별자치도", "전북").replace("전라북도", "전북")
        .replace("전라남도", "전남").replace("경상북도", "경북")
        .replace("경상남도", "경남").replace("제주특별자치도", "제주")
        .replace("제주도", "제주")
        .replace("세종특별자치시", "세종")
        .replace("남성", "남자").replace("대한민국", "전국").replace("한국", "전국"))

def _key(org: str, table: str, item: str, obj: str | None, member: str | None, prd_se: str, prd_de: str, dimensions: dict[str, str], *, include_dimensions: bool) -> str:
    base = f"ORG={org}|TBL={table}|ITM={item}|OBJ={obj}|MEMBER={member}|PRD_SE={prd_se}|PRD_DE={prd_de}"
    if not include_dimensions or len(dimensions) <= 1:
        return base
    encoded = ",".join(f"{key}:{value}" for key, value in dimensions.items())
    return f"{base}|DIMS={encoded}"


def _indicator_terms(claim: ClaimSchema) -> set[str]:
    """Keep the base statistical concept available for derived-rate Claims."""
    indicator = _normalize(claim.indicator)
    terms = {indicator} if indicator else set()
    if indicator.endswith("액"):
        terms.add(f"{indicator[:-1]}금액")
    if claim.calculation not in {"GROWTH_RATE", "DIFFERENCE", "SHARE", "RATIO", "MULTIPLE"}:
        return terms
    for suffix in (
        "\uc0c1\uc2b9\ub960", "\ud558\ub77d\ub960", "\uc99d\uac00\uc728", "\uac10\uc18c\uc728",
        "\ub4f1\ub77d\ub960", "\ubcc0\ub3d9\ub960",
    ):
        if indicator.endswith(suffix):
            base = indicator[: -len(suffix)]
            if base:
                terms.add(base)
    return terms


def _item_matches_indicator(item: str, terms: set[str]) -> bool:
    return any(item == term or item in term or term in item for term in terms if term)
