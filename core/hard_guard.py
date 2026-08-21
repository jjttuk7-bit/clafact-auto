"""Public Hard Guard with deterministic Claim-side vocabulary normalization."""
from core.hard_guard_impl import apply_hard_guard as _apply

_COMBINED_INDUSTRY = "* 도소매·숙박음식점업(GI)"

def _value_alias(value: str, table_id: str) -> str:
    compact = value.replace(" ", "")
    if table_id == "DT_1DA7E06S_NEW" and "도소매" in compact and "숙박" in compact and "음식점" in compact:
        return _COMBINED_INDUSTRY
    aliases = {"20대": "20~29세"}
    if table_id == "DT_1B80A13":
        aliases["80대"] = "80 - 84세"
    return aliases.get(value.strip(), value)

def apply_hard_guard(claim, candidate):
    dimensions = {key: _value_alias(value, candidate.tbl_id) for key, value in (claim.dimension or {}).items()}
    population = _value_alias(claim.population, candidate.tbl_id) if claim.population else claim.population
    return _apply(claim.model_copy(update={"dimension": dimensions or claim.dimension, "population": population}), candidate)
