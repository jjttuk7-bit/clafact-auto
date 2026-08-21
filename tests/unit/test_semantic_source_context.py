from pathlib import Path

from core.data_loader import load_standard_concepts
from core.semantic_normalizer import normalize_concept
from schemas.claim import ClaimSchema


def test_generic_price_index_uses_unique_indicator_named_in_source_sentence() -> None:
    concepts = load_standard_concepts(
        Path(__file__).resolve().parents[2] / "data" / "semantic_standard" / "concept_seed_v1.json"
    )
    claim = ClaimSchema(
        claim_id="price-index",
        source_sentence="수출물가지수는 전년 동월 대비 10.7% 올랐다.",
        indicator="물가지수",
        value=10.7,
        unit="%",
        time="2025년 1월",
        frequency="월",
        calculation="GROWTH_RATE",
        parse_status="AUTO_OK",
    )

    result = normalize_concept(claim, concepts)

    assert result.status == "MATCHED"
    assert result.standard_key == "export_price_index"
    assert result.matched_alias == "수출물가지수"


def test_nonregular_worker_indicator_is_a_registered_concept() -> None:
    concepts = load_standard_concepts(
        Path(__file__).resolve().parents[2] / "data" / "semantic_standard" / "concept_seed_v1.json"
    )
    claim = ClaimSchema(
        claim_id="nonregular-worker",
        source_sentence="임금근로자 중 비정규직 근로자 비중은 38.2%였다.",
        indicator="비정규직 규모/비율",
        value=38.2,
        unit="%",
        time="2025년",
        frequency="년",
        calculation="SHARE",
        parse_status="AUTO_OK",
    )

    result = normalize_concept(claim, concepts)

    assert result.status == "MATCHED"
    assert result.standard_key == "nonregular_worker"
