from core.direct_value_child_guard import enrich_target_qualifiers_from_context
from schemas.claim import ClaimSchema


def test_context_age_is_not_added_to_unrelated_direct_value_claim() -> None:
    claim = ClaimSchema(
        claim_id="CONTEXT-UNRELATED-KO",
        source_sentence="소비자물가는 5.5%였다.",
        indicator="소비자물가",
        value=5.5,
        unit="%",
        time="2025년 1분기",
        frequency="분기",
        calculation="DIRECT_VALUE",
        parse_status="AUTO_OK",
    )
    context = "25~29세 고졸 실업률은 5.5%였다. 소비자물가는 5.5%였다."

    result = enrich_target_qualifiers_from_context(
        claim, target_expression="5.5%", article_context=context
    )

    assert result == claim
