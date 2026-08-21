"""Public deterministic slot enrichment with official-evidence operand routing."""

from core import deterministic_slot_enricher_impl as _impl
from core.deterministic_slot_enricher_impl import ExplicitSlotValues
from core.unit_normalizer import compatible_units
from schemas.claim import ClaimSchema

__all__ = ["ExplicitSlotValues", "infer_explicit_slots", "apply_explicit_slots"]


def _normalize_comparison_phrases(source: str) -> str:
    replacements = {
        "전년 동기 대비": "전년 대비",
        "전년 같은 달 대비": "전년 동월 대비",
        "지난해 같은 달 대비": "작년 동월 대비",
        "지난해보다": "작년 대비",
        "전년보다": "전년 대비",
    }
    for old, new in replacements.items():
        source = source.replace(old, new)
    return source


def infer_explicit_slots(source_sentence: str) -> ExplicitSlotValues:
    return _impl.infer_explicit_slots(_normalize_comparison_phrases(source_sentence))


def apply_explicit_slots(claim: ClaimSchema) -> ClaimSchema:
    normalized_source = _normalize_comparison_phrases(claim.source_sentence)
    temporary = claim.model_copy(update={"source_sentence": normalized_source})
    enriched = _impl.apply_explicit_slots(temporary).model_copy(update={"source_sentence": claim.source_sentence})
    comparison = dict(enriched.comparison or {})
    comparison_type = str(comparison.get("type", "")).upper()
    if (
        claim.calculation is None
        and comparison_type in {"YEAR_OVER_YEAR", "MONTH_OVER_MONTH", "QUARTER_OVER_QUARTER"}
        and not compatible_units(enriched.unit or "", "%")
    ):
        comparison["operand_source"] = "OFFICIAL_EVIDENCE"
        return enriched.model_copy(update={
            "comparison": comparison, "calculation": "DIFFERENCE",
            "parse_status": "AUTO_OK", "parse_reason": None,
        })
    return enriched
