from pathlib import Path

from core.semantic_normalizer_v3 import normalize_concept_v3
from core.semantic_standard_v2 import load_semantic_standard_v2
from schemas.claim import ClaimSchema


CONCEPTS = load_semantic_standard_v2(Path("data/semantic_standard/concept_seed_v1.json"), Path("data/semantic_standard/concept_overlay_v3.json"))


def _claim(indicator, source="통계 수치가 발표됐다"):
    return ClaimSchema(claim_id="c", source_sentence=source, indicator=indicator, value=1, unit="명", time="2025년", calculation="DIRECT_VALUE", parse_status="AUTO_OK")


def test_generic_rate_uses_unique_source_concept() -> None:
    concept = normalize_concept_v3(_claim("증가율", "출생아 수가 3.8% 증가했다"), CONCEPTS)
    assert concept.standard_key == "birth_count"
    assert concept.status == "MATCHED"


def test_explicit_unknown_indicator_is_registered_as_observed_concept() -> None:
    concept = normalize_concept_v3(_claim("새로운 명시 지표"), CONCEPTS)
    assert concept.concept_id.startswith("OBSERVED:")
    assert concept.kosis_search_terms == ["새로운 명시 지표"]
    assert concept.status == "MATCHED"


def test_missing_indicator_remains_unresolved() -> None:
    assert normalize_concept_v3(_claim(None), CONCEPTS).status == "UNRESOLVED"
