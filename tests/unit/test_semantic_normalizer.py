from pathlib import Path

import pytest

from core.data_loader import SemanticStandardRecord, load_standard_concepts
from core.semantic_normalizer import normalize_concept
from schemas.claim import ClaimSchema


CONCEPTS = [
    SemanticStandardRecord("C001", "고용률", "employment_rate", ("취업률",)),
    SemanticStandardRecord("C002", "실업률", "unemployment_rate", ("실업율",)),
]


def claim(indicator: str | None) -> ClaimSchema:
    return ClaimSchema(claim_id="C1", source_sentence="문장", indicator=indicator, parse_status="AUTO_OK")


def test_normalize_concept_matches_exact_alias() -> None:
    result = normalize_concept(claim("취업률"), CONCEPTS)

    assert result.concept_id == "C001"
    assert result.matched_alias == "취업률"
    assert result.status == "MATCHED"


def test_normalize_concept_matches_canonical_name() -> None:
    result = normalize_concept(claim("실업률"), CONCEPTS)

    assert result.concept_id == "C002"
    assert result.status == "MATCHED"


def test_normalize_concept_matches_normalized_alias() -> None:
    result = normalize_concept(claim(" 취 업 률 "), CONCEPTS)

    assert result.concept_id == "C001"
    assert result.matched_alias == "취업률"


def test_normalize_concept_uses_similarity_only_above_threshold() -> None:
    result = normalize_concept(claim("실업율"), CONCEPTS, similarity_threshold=0.95)

    assert result.concept_id == "C002"
    assert result.status == "MATCHED"


def test_normalize_concept_routes_unknown_indicator_to_unresolved() -> None:
    result = normalize_concept(claim("국내총생산"), CONCEPTS)

    assert result.status == "UNRESOLVED"
    assert result.concept_id == "UNRESOLVED"


def test_normalize_concept_routes_missing_indicator_to_unresolved() -> None:
    result = normalize_concept(claim(None), CONCEPTS)

    assert result.status == "UNRESOLVED"


def test_normalize_concept_does_not_force_ambiguous_similarity_match() -> None:
    ambiguous = [
        SemanticStandardRecord("C010", "가나다", "one", ()),
        SemanticStandardRecord("C011", "가라다", "two", ()),
    ]

    result = normalize_concept(claim("가마다"), ambiguous, similarity_threshold=0.6)

    assert result.status == "UNRESOLVED"


@pytest.mark.parametrize(
    ("indicator", "standard_key"),
    [
        ("총인구", "total_population"),
        ("소비자물가 상승률", "inflation_rate"),
        ("가공식품 물가", "inflation_rate"),
        ("전산업생산", "all_industry_production_index"),
        ("건설수주", "construction_order_value"),
        ("광공업생산", "mining_manufacturing_production_index"),
        ("제조업생산", "manufacturing_production_index"),
        ("과수원 면적", "cultivated_area"),
        ("해외건설", "overseas_construction_orders"),
        ("해외직접투자액", "outward_foreign_direct_investment"),
        ("실업자 수", "unemployed_count"),
        ("1인당 GDP", "gross_domestic_product_per_capita"),
        ("수출량", "export_quantity"),
        ("수입량", "import_quantity"),
        ("인구 자연증감", "natural_population_change"),
    ],
)
def test_gold_standard_indicators_match_canonical_concepts(
    indicator: str, standard_key: str
) -> None:
    path = Path(__file__).resolve().parents[2] / "data" / "semantic_standard" / "concept_seed_v1.json"
    result = normalize_concept(claim(indicator), load_standard_concepts(path))

    assert result.status == "MATCHED"
    assert result.matched_alias == indicator
    assert result.standard_key == standard_key

def test_normalize_concept_uses_dimension_member_with_indicator() -> None:
    contextual = [SemanticStandardRecord(
        "CPI_DETAIL:A02A01701", "배추 소비자물가지수", "cpi_detail:A02A01701",
        ("배추 물가",), ("배추 소비자물가지수", "품목별 소비자물가지수 배추"),
    )]
    contextual_claim = claim("물가").model_copy(update={"dimension": {"product": "배추"}})

    result = normalize_concept(contextual_claim, contextual)

    assert result.concept_id == "CPI_DETAIL:A02A01701"
    assert result.matched_alias == "배추 물가"
    assert result.kosis_search_terms == ["배추 소비자물가지수", "품목별 소비자물가지수 배추"]
