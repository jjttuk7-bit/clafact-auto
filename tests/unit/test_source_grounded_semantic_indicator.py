from core.data_loader import SemanticStandardRecord
from core.semantic_indicator_alignment import align_claim_indicator_to_concept
from core.semantic_normalizer import normalize_concept
from schemas.claim import ClaimSchema


CONCEPTS = [
    SemanticStandardRecord("birth", "출생아 수", "birth_count", ("출생자 수", "출생아")),
    SemanticStandardRecord("population", "총인구", "total_population", ("총인구",)),
]


def _misparsed_birth() -> ClaimSchema:
    return ClaimSchema(
        claim_id="birth-2024",
        source_sentence="행정안전부는 2024년 출생자 수가 24만2334명으로 집계됐다고 밝혔다.",
        indicator="총인구",
        value=242_334,
        unit="명",
        time="2024",
        frequency="년",
        calculation="DIRECT_VALUE",
        parse_status="AUTO_OK",
    )


def test_semantic_mapping_uses_unique_grounded_value_despite_period_number() -> None:
    result = normalize_concept(_misparsed_birth(), CONCEPTS)

    assert result.concept_id == "birth"
    assert result.matched_alias == "출생자 수"


def test_indicator_alignment_repairs_source_contradicted_slot_with_period_number() -> None:
    concept = normalize_concept(_misparsed_birth(), CONCEPTS)

    repaired = align_claim_indicator_to_concept(_misparsed_birth(), concept)

    assert repaired.indicator == "출생아 수"


def test_same_target_value_twice_does_not_force_source_indicator() -> None:
    claim = _misparsed_birth().model_copy(
        update={
            "source_sentence": "2024년 총인구 통계 24만2334명과 출생자 수 24만2334명이 함께 제시됐다."
        }
    )

    result = normalize_concept(claim, CONCEPTS)

    assert result.concept_id == "population"
