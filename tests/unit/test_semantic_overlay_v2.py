from pathlib import Path

from core.semantic_standard_v2 import load_semantic_standard_v2
from core.semantic_normalizer import normalize_concept
from schemas.claim import ClaimSchema


BASE = Path("data/semantic_standard/concept_seed_v1.json")
OVERLAY = Path("data/semantic_standard/concept_overlay_v2.json")


def _claim(indicator: str) -> ClaimSchema:
    return ClaimSchema(
        claim_id="c",
        source_sentence=f"{indicator}는 1이었다.",
        indicator=indicator,
        value=1,
        unit="명",
        time="2025년",
        calculation="DIRECT_VALUE",
        parse_status="AUTO_OK",
    )


def test_v2_semantic_overlay_maps_repeated_employment_birth_and_inactivity_labels() -> None:
    concepts = load_semantic_standard_v2(BASE, OVERLAY)

    assert normalize_concept(_claim("취업자"), concepts).concept_id == "C000008"
    assert normalize_concept(_claim("15세 이상 취업자"), concepts).concept_id == "C000008"
    assert normalize_concept(_claim("사망자"), concepts).concept_id == "C000018"
    assert normalize_concept(_claim("합계출산율"), concepts).standard_key == "total_fertility_rate"
    assert normalize_concept(_claim("쉬었음 인구"), concepts).standard_key == "inactive_population_resting"
