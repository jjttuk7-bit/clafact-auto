"""Structural compatibility checks before semantic scoring."""

import re

from core.claim_dimensions import normalized_dimension_members
from core.region_aliases import NATIONAL_REGION_ALIASES
from core.unit_normalizer import compatible_units
from schemas.candidate import HardGuardResult


def apply_hard_guard(c, x):
    rejected = []
    if (
        x.metadata_status in {"LIVE_SEARCH_UNRESOLVED", "OFFICIAL_ITEM_METADATA_UNAVAILABLE"}
        or (x.metadata_status == "OFFICIAL_PERIOD_METADATA_UNAVAILABLE" and not _safe(c, x))
        or (c.frequency and x.metadata_status == "OFFICIAL_ITEM_METADATA_READY" and not x.frequency)
    ):
        rejected += ["METADATA_INCOMPLETE"]
    if _freq(c, x): rejected += ["FREQUENCY_CONFLICT"]
    if _unit(c, x): rejected += ["UNIT_CONFLICT"]
    if _age(c, x): rejected += ["AGE_DIMENSION_REQUIRED"]
    if _population(c, x): rejected += ["POPULATION_DIMENSION_CONFLICT"]
    if c.dimension and "sex" in c.dimension and not _has(x, "\uc131\ubcc4"):
        rejected += ["SEX_DIMENSION_REQUIRED"]
    if c.region and c.region not in NATIONAL_REGION_ALIASES and not any(
        _has(x, term) for term in ("\uc2dc\ub3c4", "\uc9c0\uc5ed", "\ud589\uc815", "\uc74d\uba74")
    ):
        rejected += ["REGION_GRANULARITY_CONFLICT"]
    if _dim(c, x): rejected += ["DIMENSION_MEMBER_CONFLICT"]
    if _time(c, x): rejected += ["TIME_NOT_AVAILABLE"]
    if any(term in c.source_sentence for term in ("\uc804\ub9dd", "\uc608\uce21", "\uc608\uc0c1")):
        rejected += ["FORECAST_CLAIM"]
    return HardGuardResult(passed=not rejected, reject_codes=rejected)


def _safe(c, x):
    return bool(x.core_item_ids and x.dimension_member_codes and x.frequency and not _freq(c, x))


def _freq(c, x):
    return bool(c.frequency and x.frequency and _key(c.frequency) not in {_key(v) for v in x.frequency.split("|")})


def _unit(c, x):
    if c.calculation == "DIFFERENCE" and _key(c.unit or "") in {"%p", "%\ud3ec\uc778\ud2b8", "\ud37c\uc13c\ud2b8\ud3ec\uc778\ud2b8", "percentagepoints"}:
        return not any(_key(v) in {"%", "\ud37c\uc13c\ud2b8"} for v in x.unit_names)
    if c.calculation in {"GROWTH_RATE", "SHARE", "RATIO", "MULTIPLE"}:
        return False
    return bool(c.unit and x.unit_names and not any(compatible_units(c.unit, value) for value in x.unit_names))


def _age(c, x):
    if not c.population or "\uc138" not in c.population or _has(x, "\uc5f0\ub839"):
        return False
    requested = _key(c.population).replace("\uacc4", "")
    scope = _key(" ".join([x.tbl_name, *x.core_item_names, *x.binding_scope_terms]))
    return not (
        (requested and requested in scope)
        or (
            x.source_stat_id == "OFFICIAL_RECURRING_DOMAIN_BINDING"
            and "15\uc138\uc774\uc0c1" in requested
            and "\uacbd\uc81c\ud65c\ub3d9\uc778\uad6c" in scope
        )
    )


def _population(c, x):
    if not c.population or "세" in c.population:
        return False
    population_key = _key(c.population)
    if not any(marker in population_key for marker in ("청년", "고령", "노인", "아동", "청소년")):
        return False
    requested = _population_key(c.population)
    if requested in {"", "계", "전체", "전국"}:
        return False
    official = {
        _population_key(value)
        for values in x.dimension_members.values()
        for value in values
    }
    scope = _population_key(" ".join([x.tbl_name, *x.core_item_names, *x.binding_scope_terms]))
    return not (requested in official or requested in scope)



def _dim(c, x):
    if not c.dimension or not x.dimension_members:
        return False
    official = {_key(value) for values in x.dimension_members.values() for value in values}
    scope = _key(" ".join([x.tbl_name, *x.core_item_names, *x.binding_scope_terms]))
    return any(
        not (member in official or member in scope or sum(member in value for value in official) == 1)
        for member in _coordinate_members(c)
    )


def _coordinate_members(c):
    """Exclude a methodology label only when its age coordinate is explicit elsewhere."""
    members = []
    has_age_population = bool(c.population and "\uc138" in c.population)
    for key, values in normalized_dimension_members(c.dimension).items():
        normalized_key = _key(key)
        for value in values:
            normalized_value = _key(value)
            is_age_methodology = (
                has_age_population
                and normalized_key in {"\uae30\uc900", "\ube44\uad50\uae30\uc900"}
                and normalized_value.startswith("\uad6d\uc81c\ube44\uad50")
            )
            if not is_age_methodology:
                members.append(normalized_value)
    return members


def _time(c, x):
    if not c.time or not x.start_period or not x.end_period:
        return False
    match = re.search(r"\d{4}", c.time)
    if not match:
        return False
    try:
        year = int(match.group())
        return year < int(x.start_period[:4]) or year > int(x.end_period[:4])
    except ValueError:
        return False


def _has(x, text):
    return any(text in name for name in x.dimension_names)


def _key(value):
    normalized = re.sub(r"\s+", "", value).casefold()
    normalized = {
        "monthly": "\uc6d4", "month": "\uc6d4", "m": "\uc6d4",
        "yearly": "\ub144", "year": "\ub144", "annual": "\ub144", "y": "\ub144", "\uc5f0": "\ub144", "\uc5f0\uac04": "\ub144",
        "quarterly": "\ubd84\uae30", "quarter": "\ubd84\uae30", "q": "\ubd84\uae30", "halfyear": "\ubc18\uae30",
    }.get(normalized, normalized)
    return (
        normalized.replace("~", "").replace("-", "")
        .replace("\uc5ec\uc131", "\uc5ec\uc790").replace("\ub0a8\uc131", "\ub0a8\uc790")
        .replace("\ud569\uacc4", "\uacc4").replace("\ucd1d\uacc4", "\uacc4").replace("\uc804\uccb4", "\uacc4")
        .replace("\ub300\ud55c\ubbfc\uad6d", "\uc804\uad6d").replace("\ud55c\uad6d", "\uc804\uad6d")
    )


def _population_key(value):
    return _key(value).replace("인구", "").replace("층", "")
