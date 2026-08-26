from tools.run_direct_value_unseen_news_acceptance import CASES, _claim_matches_expected


def test_unseen_cases_include_release_table_direct_value_generalization() -> None:
    cases = {case["case_id"]: case for case in CASES}
    case = cases["UNSEEN_RESTING_POPULATION_PARAPHRASE"]
    assert case["expected_value"] == 2_390_000.0
    assert "쉬었음" in case["article_text"]
    assert "2025년 5월" in case["article_text"]

def test_unseen_acceptance_compares_claim_value_in_base_measurement_unit() -> None:
    assert _claim_matches_expected({"value": 239.0, "unit": "만 명"}, 2_390_000.0)
    assert _claim_matches_expected({"value": 3.8, "unit": "%"}, 3.8)
