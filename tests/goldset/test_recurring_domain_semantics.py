from pathlib import Path

import pytest

from core.semantic_normalizer_v3 import normalize_concept_v3
from core.semantic_standard_v2 import load_semantic_standard_v2
from schemas.claim import ClaimSchema


CONCEPTS = load_semantic_standard_v2(
    Path("data/semantic_standard/concept_seed_v1.json"),
    Path("data/semantic_standard/concept_overlay_v3.json"),
)


def _claim(indicator: str) -> ClaimSchema:
    return ClaimSchema(
        claim_id="C1",
        source_sentence=f"2025년 {indicator}은 공식 통계로 발표됐다.",
        indicator=indicator,
        value=1,
        unit="명",
        time="2025년",
        frequency="년",
        calculation="DIRECT_VALUE",
        parse_status="AUTO_OK",
    )


@pytest.mark.parametrize(
    ("indicator", "expected_standard_key"),
    [
        ("취업자 수 증가 폭", "employment_count"),
        ("국내 취업자 수", "employment_count"),
        ("출생아 수 증가율", "birth_count"),
        ("생활물가", "living_price_index"),
        ("전체 산업생산", "all_industry_production_index"),
    ],
)
def test_recurring_core_domain_expression_maps_to_registered_official_concept(
    indicator: str, expected_standard_key: str
) -> None:
    concept = normalize_concept_v3(_claim(indicator), CONCEPTS)

    assert concept.status == "MATCHED"
    assert concept.standard_key == expected_standard_key
    assert not concept.concept_id.startswith("OBSERVED:")


def test_generic_price_index_is_not_forced_to_consumer_price() -> None:
    concept = normalize_concept_v3(_claim("물가지수"), CONCEPTS)

    assert concept.standard_key != "consumer_price"
