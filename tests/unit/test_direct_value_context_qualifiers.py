from core.direct_value_child_guard import enrich_target_qualifiers_from_context
from schemas.claim import ClaimSchema


def _claim() -> ClaimSchema:
    return ClaimSchema(
        claim_id="CONTEXT-AGE", source_sentence="올해 1분기 고졸 실업률은 5.5%였다.",
        indicator="실업률", value=5.5, unit="%", time="2025년 1분기",
        frequency="분기", dimension={"학력": "고졸"},
        calculation="DIRECT_VALUE", parse_status="AUTO_OK",
    )


def test_unique_article_context_age_is_added_to_target_claim() -> None:
    context = (
        "주 취업 연령대인 20대 후반(25~29세) 고졸 실업률은 "
        "지난 1분기에 5.5%였다. 올해 1분기 고졸 실업률은 5.5%였다."
    )

    result = enrich_target_qualifiers_from_context(
        _claim(), target_expression="5.5%", article_context=context
    )

    assert result.population == "25~29세"
    assert result.dimension == {"학력": "고졸", "age": "25~29세"}


def test_conflicting_context_ages_remain_unresolved() -> None:
    context = "25~29세 고졸 실업률은 5.5%였다. 30대 고졸 실업률도 5.5%였다."

    assert enrich_target_qualifiers_from_context(
        _claim(), target_expression="5.5%", article_context=context
    ) == _claim()

