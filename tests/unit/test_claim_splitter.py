from core.claim_splitter import split_complex_claim


def test_keeps_single_numeric_claim_as_one_sentence() -> None:
    sentence = "2024년 고용률은 70%였다."

    assert split_complex_claim(sentence) == [sentence]


def test_splits_clauses_joined_by_and_when_both_have_numbers() -> None:
    sentence = "2023년 고용률은 60%였고 2024년 고용률은 61%였다."

    assert split_complex_claim(sentence) == ["2023년 고용률은 60%", "2024년 고용률은 61%였다."]


def test_splits_comma_delimited_repeated_numeric_claims() -> None:
    sentence = "서울은 10명, 부산은 20명으로 집계됐다."

    assert split_complex_claim(sentence) == ["서울은 10명", "부산은 20명으로 집계됐다."]


def test_does_not_split_a_single_quantity_with_a_comma() -> None:
    sentence = "예산은 1,000억원이었다."

    assert split_complex_claim(sentence) == [sentence]
