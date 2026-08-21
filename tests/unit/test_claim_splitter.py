import json
from pathlib import Path

import pytest

from core.claim_splitter import detect_structural_multi_claim, split_complex_claim


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



def test_detects_all_directly_reviewed_p0_multi_claims() -> None:
    fixture = Path(__file__).parents[1] / "fixtures" / "admission_pre_split_p0_gold.jsonl"
    rows = [json.loads(line) for line in fixture.read_text(encoding="utf-8").splitlines()]

    assert len(rows) == 16
    assert all(detect_structural_multi_claim(row["source_sentence"]) for row in rows)


def test_does_not_split_one_direct_value_with_only_a_base_year_annotation() -> None:
    sentence = "지난달 소비자물가지수는 116.31(2020년=100)이었다."

    assert not detect_structural_multi_claim(sentence)



def test_ignores_dates_periods_scope_counts_and_reference_values_in_eligible_gold_cases() -> None:
    fixture = Path(__file__).parents[1] / "fixtures" / "admission_pre_split_false_positive_gold.jsonl"
    rows = [json.loads(line) for line in fixture.read_text(encoding="utf-8").splitlines()]

    assert len(rows) == 23
    assert not any(detect_structural_multi_claim(row["source_sentence"]) for row in rows)

def test_splits_current_value_and_year_over_year_change_into_complete_claims() -> None:
    sentence = "지난달 제조업 취업자는 439만7000명으로 전년 동월 대비 12만4000명 줄었다."

    assert split_complex_claim(sentence) == [
        "지난달 제조업 취업자는 439만7000명이다.",
        "지난달 제조업 취업자는 전년 동월 대비 12만4000명 줄었다.",
    ]

import pytest


@pytest.mark.parametrize(
    ("sentence", "expected"),
    [
        (
            "다만 반도체를 중심으로 수출 실적이 회복되면서 작년 산업 생산은 1.7% 늘어 전년(1%)에 비해 증가 폭이 커졌다.",
            [
                "작년 산업 생산은 1.7% 늘었다.",
                "작년 산업 생산은 전년(1%)에 비해 증가 폭이 커졌다.",
            ],
        ),
        (
            "지난달 외식 물가 역시 전년 대비 3.0% 오르면서 2개월 연속 3% 상승을 기록했다.",
            [
                "지난달 외식 물가는 전년 대비 3.0% 올랐다.",
                "지난달 외식 물가는 2개월 연속 3% 상승을 기록했다.",
            ],
        ),
        (
            "국가데이터처가 29일 발표한 '8월 인구동향'에 따르면 지난 8월 출생아 수는 1년 전보다 764명(3.8%) 증가한 2만867명이다.",
            [
                "지난 8월 출생아 수는 1년 전보다 764명(3.8%) 증가했다.",
                "지난 8월 출생아 수는 2만867명이다.",
            ],
        ),
    ],
)
def test_splits_remaining_directly_reviewed_multi_claim_patterns(
    sentence: str, expected: list[str]
) -> None:
    assert split_complex_claim(sentence) == expected