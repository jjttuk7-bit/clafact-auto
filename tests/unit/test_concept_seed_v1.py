import ast
from pathlib import Path

from core.data_loader import load_standard_concepts
from core.semantic_normalizer import normalize_concept
from schemas.claim import ClaimSchema


SEED_PATH = Path("data/semantic_standard/concept_seed_v1.json")
APP_PATH = Path("app/streamlit_app.py")


def _claim(indicator: str) -> ClaimSchema:
    return ClaimSchema(
        claim_id="concept-seed-test",
        source_sentence="테스트 문장",
        indicator=indicator,
        parse_status="AUTO_OK",
    )


def test_concept_seed_v1_contains_40_unique_verified_concepts() -> None:
    concepts = load_standard_concepts(SEED_PATH)

    assert len(concepts) == 40
    assert len({concept.concept_id for concept in concepts}) == 40
    assert len({concept.standard_key for concept in concepts}) == 40


def test_concept_seed_v1_maps_representative_claim_indicators() -> None:
    concepts = load_standard_concepts(SEED_PATH)

    assert normalize_concept(_claim("수출액"), concepts).standard_key == "export_value"
    assert normalize_concept(_claim("국내총생산(GDP)"), concepts).standard_key == "gross_domestic_product"
    assert normalize_concept(_claim("1인 가구 수"), concepts).standard_key == "one_person_household_count"

def test_export_value_concept_uses_official_total_trade_search_vocabulary() -> None:
    concepts = load_standard_concepts(SEED_PATH)
    result = normalize_concept(_claim("수출액"), concepts)
    assert result.kosis_search_terms[0] == "수출입총괄"
    assert "국가별 수출액 수입액" in result.kosis_search_terms


def test_concept_seed_v1_keeps_employment_binding_compatible_standard_key() -> None:
    concepts = load_standard_concepts(SEED_PATH)

    result = normalize_concept(_claim("취업자 수"), concepts)

    assert result.status == "MATCHED"
    assert result.standard_key == "employment_count"

def test_streamlit_app_uses_concept_seed_v1_as_the_default_standard() -> None:
    module = ast.parse(APP_PATH.read_text(encoding="utf-8"))
    standard_path = next(
        node
        for node in module.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "STANDARD_PATH" for target in node.targets)
    )

    assert isinstance(standard_path.value, ast.BinOp)
    assert isinstance(standard_path.value.right, ast.Constant)
    assert standard_path.value.right.value == "concept_seed_v1.json"
