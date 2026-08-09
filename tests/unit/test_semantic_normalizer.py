from core.data_loader import SemanticStandardRecord
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
