"""Public evidence resolver with registered coordinate normalization."""
import re
from core.claim_candidate_aliases import normalize_claim_for_candidate
from core.evidence_resolver_impl import *  # noqa: F403
from core.evidence_resolver_impl import resolve_evidence_cell as _resolve

def _normalize_claim_aliases(claim, candidate):
    return normalize_claim_for_candidate(claim, candidate)

def resolve_evidence_cell(claim, candidate):
    names = [name[:-1] if name.endswith("계") and len(name) > 1 else name for name in candidate.core_item_names]
    if candidate.source_stat_id == "OFFICIAL_RECURRING_DOMAIN_BINDING" and len(names) == 1 and claim.indicator:
        names = [claim.indicator]
    selected = candidate if names == candidate.core_item_names else candidate.model_copy(update={"core_item_names": names})
    aliases = {"연간":"년","연":"년","annual":"년","yearly":"년","monthly":"월","month":"월","quarterly":"분기","quarter":"분기"}
    frequency = aliases.get((claim.frequency or "").strip().casefold(), claim.frequency)
    normalized_claim = _normalize_claim_aliases(claim, candidate)
    if frequency != normalized_claim.frequency:
        normalized_claim = normalized_claim.model_copy(update={"frequency": frequency})
    cell = _resolve(normalized_claim, selected)
    half = re.fullmatch(r"(?P<year>\d{4})년\s*(?P<half>상|하)반기", (claim.time or "").strip())
    if half and cell.status == "CONFIRMED":
        period = f"{half['year']}0{1 if half['half'] == '상' else 2}"
        cell = cell.model_copy(update={"prd_se":"H","prd_de":period,"canonical_key":cell.canonical_key.replace(f"PRD_SE={cell.prd_se}","PRD_SE=H").replace(f"PRD_DE={cell.prd_de}",f"PRD_DE={period}")})
    return cell
