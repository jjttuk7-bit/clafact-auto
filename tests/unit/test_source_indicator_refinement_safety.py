from schemas.claim import ClaimSchema
from core.source_indicator_refinement import refine_source_indicator


def test_export_growth_is_not_misclassified_as_country_gdp_growth() -> None:
    claim = ClaimSchema(
        claim_id="C1",
        source_sentence="반도체 수출은 올해 9.7% 성장했다.",
        indicator="수출액",
        value=9.7,
        unit="%",
        time="2025",
        frequency="Y",
        calculation="DIRECT_VALUE",
        parse_status="AUTO_OK",
    )

    refined = refine_source_indicator(claim, target_expression="9.7%")

    assert refined.indicator == "수출액"
