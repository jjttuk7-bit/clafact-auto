"""Versioned recurring-domain bindings applied to official candidates."""
import json, re
from pathlib import Path

from core.claim_dimensions import normalized_dimension_members
from schemas.candidate import KosisCandidateSchema
_PATH = Path(__file__).resolve().parents[1] / "data" / "semantic_standard" / "kosis_bindings.json"

def seed_catalog_bindings(claim, concept, candidates):
    """Seed applicable registered official tables before live metadata hydration."""
    materialized = list(candidates)
    existing = {(item.org_id, item.tbl_id) for item in materialized}
    seeds = []
    for binding in _load():
        if not _applies(binding, claim, concept):
            continue
        identity = (str(binding.get("org_id") or ""), str(binding.get("tbl_id") or ""))
        if not all(identity) or identity in existing:
            continue
        seeds.append(KosisCandidateSchema(
            org_id=identity[0], tbl_id=identity[1], tbl_name=concept.canonical_name,
            source_stat_id="OFFICIAL_RECURRING_BINDING_SEED",
            metadata_status="LIVE_SEARCH_UNRESOLVED",
        ))
        existing.add(identity)
    return [*seeds, *materialized]
def apply_catalog_binding(claim, concept, candidates):
    materialized = list(candidates)
    for binding in _load():
        if not _applies(binding, claim, concept):
            continue
        bound = [x for x in materialized if x.tbl_id == binding.get("tbl_id") and x.org_id == str(binding.get("org_id", x.org_id))]
        if len(bound) != 1:
            continue
        selected = _apply(bound[0], binding)
        return [selected] if selected is not None else materialized
    return materialized

def _apply(candidate, binding):
    target = binding.get("itm_id")
    update = {"source_stat_id": "OFFICIAL_RECURRING_DOMAIN_BINDING"}
    if scope_terms := _strings(binding.get("scope_terms")):
        update["binding_scope_terms"] = scope_terms
    if target is not None:
        pairs = [(i, n) for i, n in zip(candidate.core_item_ids, candidate.core_item_names) if i == str(target)]
        if len(pairs) != 1:
            return None
        update.update({"core_item_ids": [pairs[0][0]], "core_item_names": [pairs[0][1]], "item_units": ({str(target): candidate.item_units[str(target)]} if str(target) in candidate.item_units else {})})
    if binding.get("prd_se") and candidate.frequency:
        update["frequency"] = str(binding["prd_se"])
    requested = binding.get("dimension_codes")
    if isinstance(requested, dict):
        if not candidate.dimension_member_codes:
            return None
        members, codes = {}, {}
        for axis, code in requested.items():
            matches = [(name, value) for name, value in candidate.dimension_member_codes.get(str(axis), {}).items() if value == str(code)]
            if len(matches) != 1:
                return None
            members[str(axis)] = [matches[0][0]]
            codes[str(axis)] = {matches[0][0]: matches[0][1]}
        update.update({"dimension_members": {**candidate.dimension_members, **members}, "dimension_member_codes": {**candidate.dimension_member_codes, **codes}})
    if unit := str(binding.get("unit") or "").strip():
        update["unit_names"] = [unit]
        if target is not None:
            update["item_units"] = {str(target): unit}
    return candidate.model_copy(update=update)

def _load():
    payload = json.loads(_PATH.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, list):
        raise ValueError("KOSIS_BINDING_INVALID")
    return [item for item in payload if isinstance(item, dict)]

def _applies(binding, claim, concept):
    if binding.get("standard_key") != concept.standard_key:
        return False
    if frequencies := _strings(binding.get("frequencies")):
        if _freq(claim.frequency) not in {_freq(value) for value in frequencies}:
            return False
    text = _key(" ".join(filter(None, [claim.indicator, claim.source_sentence])))
    if terms := _strings(binding.get("indicator_contains_any")):
        if not any(_key(term) in text for term in terms):
            return False
    named_dimensions = normalized_dimension_members(claim.dimension)
    values = [_key(value) for members in named_dimensions.values() for value in members]
    axes = {_dimension_axis(key) for key in named_dimensions}
    axes.discard(None)
    if required_axes := _strings(binding.get("dimension_axis_any")):
        if not any(_dimension_axis(axis) in axes for axis in required_axes):
            return False
    if forbidden_axes := _strings(binding.get("dimension_axis_none")):
        if any(_dimension_axis(axis) in axes for axis in forbidden_axes):
            return False
    if terms := _strings(binding.get("dimension_contains_any")):
        if not any(_key(term) in value for term in terms for value in values):
            return False
    if binding.get("dimension_absent") is True and claim.dimension:
        return False
    if binding.get("age_scope_required") is True and not _has_age_scope(claim):
        return False
    if binding.get("education_scope_required") is True and not _has_education_scope(claim):
        return False
    national = claim.region in {None, "전국", "대한민국", "한국"}
    if binding.get("region_scope") == "national" and not national:
        return False
    if binding.get("region_scope") == "local" and national:
        return False
    return True

def _strings(value): return [str(item) for item in value] if isinstance(value, list) else []
def _has_age_scope(claim):
    values = [claim.population or "", *(claim.dimension or {}).values()]
    return any(re.search(r"\d+\s*(?:대|세)|청년(?:층)?|고령층", str(value)) for value in values)
def _has_education_scope(claim):
    dimensions = claim.dimension or {}
    text = " ".join([*map(str, dimensions.keys()), *map(str, dimensions.values()), str(claim.population or "")])
    return any(term in text for term in ("학력", "교육정도", "고졸", "중졸", "대졸", "전문대"))
def _freq(value):
    normalized = _key(value or "")
    return {"m":"월","month":"월","monthly":"월","월간":"월","q":"분기","quarter":"분기","quarterly":"분기","y":"년","year":"년","yearly":"년","annual":"년","연":"년","연간":"년","halfyear":"반기"}.get(normalized, normalized)
def _key(value): return re.sub(r"[\s_~\-·/'‘’\"]+", "", value).casefold()

def _dimension_axis(value):
    normalized = _key(str(value or ""))
    aliases = {
        "industry": ("산업", "업종", "직종", "industry"),
        "education": ("학력", "교육정도", "교육수준", "education"),
        "product": ("품목", "상품", "재화", "product", "item"),
        "trade_partner": ("교역국", "상대국", "국가", "수출국", "수입국", "tradepartner", "country"),
    }
    for axis, terms in aliases.items():
        if any(_key(term) in normalized for term in terms):
            return axis
    return None
