from core.claim_issue_subclassification import (
    annotate_issue_subclasses,
    classify_issue_subclass,
    summarize_issue_subclasses,
)


def _row(**overrides: str) -> dict[str, str]:
    row = {
        "Claim번호": "C1",
        "원문": "2025년 취업자는 10만 명 증가했다.",
        "남은작업": "CONTEXT_REQUIRED",
        "현재문제묶음": "CONTEXT",
        "현재사유": "CONTEXT_REQUIRED",
        "현재중단단계": "CLAIM_PARSE",
        "최신결과사유": "",
        "최신결과단계": "",
        "12개항목상태": "time=SOURCE | comparison=SOURCE",
    }
    row.update(overrides)
    return row


def test_completed_claim_is_not_selected_for_more_work() -> None:
    result = classify_issue_subclass(_row(남은작업="완료", 현재문제묶음="완료"))

    assert result.code == "DONE"
    assert result.description == "최종 판정과 근거 기록이 완료됨"


def test_context_record_assertion_is_split_before_other_numeric_patterns() -> None:
    result = classify_issue_subclass(_row(
        원문="2024년 수출액은 6,838억 달러로 역대 최대를 기록했다.",
    ))

    assert result.code == "CONTEXT_RECORD_ASSERTION"
    assert "직접 수치 주장과 기록 비교 주장" in result.solution


def test_context_multiple_non_year_values_are_split() -> None:
    result = classify_issue_subclass(_row(
        원문="취업자는 10만 명 늘었고 고용률은 1.2%포인트 상승했다.",
    ))

    assert result.code == "CONTEXT_MULTI_NUMERIC"


def test_context_single_value_with_missing_time_uses_article_context() -> None:
    result = classify_issue_subclass(_row(
        원문="취업자는 10만 명 증가했다.",
        **{"12개항목상태": "time=MISSING | comparison=SOURCE"},
    ))

    assert result.code == "CONTEXT_TIME_RECOVERY"


def test_korean_compound_value_article_day_and_range_are_not_multiple_claim_values() -> None:
    compound = classify_issue_subclass(_row(
        원문="대중 수출액이 52억3500만달러 더 많았다.",
        **{"12개항목상태": "time=MISSING | comparison=SOURCE"},
    ))
    article_day = classify_issue_subclass(_row(
        원문="친환경차 수출은 70만7853대로 집계됐다고 14일 밝혔다.",
        **{"12개항목상태": "time=MISSING | comparison=SOURCE"},
    ))
    one_range = classify_issue_subclass(_row(
        원문="모든 수입품에 10~20%의 관세를 부과하겠다고 밝혔다.",
        **{"12개항목상태": "time=MISSING | comparison=SOURCE"},
    ))

    assert compound.code == "CONTEXT_TIME_RECOVERY"
    assert article_day.code == "CONTEXT_TIME_RECOVERY"
    assert one_range.code == "CONTEXT_TIME_RECOVERY"


def test_per_person_dimension_and_worded_range_are_not_multiple_claim_values() -> None:
    per_person = classify_issue_subclass(_row(
        원문="이는 1인당 성장률을 연평균 0.4%씩 낮춘다.",
        **{"12개항목상태": "time=MISSING | comparison=SOURCE"},
    ))
    worded_range = classify_issue_subclass(_row(
        원문="모든 수입품에 10% 내지 20%의 관세를 부과한다.",
        **{"12개항목상태": "time=MISSING | comparison=SOURCE"},
    ))

    assert per_person.code == "CONTEXT_TIME_RECOVERY"
    assert worded_range.code == "CONTEXT_TIME_RECOVERY"


def test_two_distinct_korean_values_are_still_multiple_numeric_claims() -> None:
    result = classify_issue_subclass(_row(
        원문="수출액은 99억8000만달러이고 관련 산업은 30억5000만달러였다.",
    ))

    assert result.code == "CONTEXT_MULTI_NUMERIC"


def test_latest_reason_has_priority_over_original_group() -> None:
    result = classify_issue_subclass(_row(
        현재문제묶음="OFFICIAL_PATH",
        현재사유="CONTEXT_REQUIRED",
        최신결과단계="KOSIS_METADATA",
        최신결과사유="KOSIS_METADATA_UNAVAILABLE",
    ))

    assert result.code == "OFFICIAL_METADATA_LOOKUP"


def test_stable_reason_codes_define_semantic_and_publication_subclasses() -> None:
    semantic = classify_issue_subclass(_row(
        현재문제묶음="SEMANTIC",
        최신결과사유="AMBIGUOUS_MARGIN",
    ))
    publication = classify_issue_subclass(_row(
        현재문제묶음="VALUE_PUBLICATION",
        최신결과사유="AS_OF_UNAVAILABLE",
    ))

    assert semantic.code == "SEMANTIC_AMBIGUOUS"
    assert publication.code == "VALUE_ARTICLE_TIME_UNAVAILABLE"


def test_missing_slots_split_hard_guard_and_coordinate_work() -> None:
    hard_guard = classify_issue_subclass(_row(
        현재문제묶음="HARD_GUARD",
        최신결과사유="NO_HARD_GUARD_CANDIDATE",
        **{"12개항목상태": "time=MISSING | unit=SOURCE"},
    ))
    coordinate = classify_issue_subclass(_row(
        현재문제묶음="COORDINATE",
        최신결과사유="NO_EVIDENCE_COORDINATE_CANDIDATE",
        **{"12개항목상태": "dimension=MISSING | time=SOURCE"},
    ))

    assert hard_guard.code == "HARD_GUARD_PERIOD"
    assert coordinate.code == "COORDINATE_DIMENSION"


def test_calculation_text_selects_record_then_change_rate() -> None:
    record = classify_issue_subclass(_row(
        현재문제묶음="CALCULATION",
        원문="수출액은 역대 최대였다.",
        최신결과사유="CALCULATION_EVIDENCE_PLAN_UNRESOLVED",
    ))
    change = classify_issue_subclass(_row(
        현재문제묶음="CALCULATION",
        원문="취업자는 전년보다 3.2% 증가했다.",
        최신결과사유="CALCULATION_EVIDENCE_PLAN_UNRESOLVED",
    ))

    assert record.code == "CALCULATION_RECORD_HISTORY"
    assert change.code == "CALCULATION_CHANGE_RATE"


def test_annotation_ranks_by_frequency_and_selects_at_most_twenty() -> None:
    rows = [
        _row(Claim번호=f"C{index:02d}", 원문="취업자는 10만 명 증가했다.")
        for index in range(1, 23)
    ]
    rows += [
        _row(
            Claim번호=f"M{index:02d}",
            원문="취업자는 10만 명 늘었고 고용률은 1.2%포인트 상승했다.",
        )
        for index in range(1, 4)
    ]
    rows.append(_row(Claim번호="DONE", 남은작업="완료", 현재문제묶음="완료"))

    annotated = annotate_issue_subclasses(rows)
    generic = [row for row in annotated if row["세부문제유형"] == "CONTEXT_GENERAL_REPARSE"]
    multi = [row for row in annotated if row["세부문제유형"] == "CONTEXT_MULTI_NUMERIC"]

    assert {row["처리우선순위"] for row in generic} == {"1"}
    assert {row["처리우선순위"] for row in multi} == {"2"}
    assert sum(bool(row["대표실행묶음"]) for row in generic) == 20
    assert sum(bool(row["대표실행묶음"]) for row in multi) == 3
    assert next(row for row in annotated if row["Claim번호"] == "DONE")["대표실행묶음"] == ""


def test_summary_reconciles_remaining_and_first_batch() -> None:
    rows = annotate_issue_subclasses([
        _row(Claim번호="C1", 원문="취업자는 10만 명 증가했다."),
        _row(Claim번호="C2", 원문="취업자는 20만 명 증가했다."),
        _row(
            Claim번호="M1",
            원문="취업자는 10만 명 늘었고 고용률은 1.2%포인트 상승했다.",
        ),
        _row(Claim번호="DONE", 남은작업="완료", 현재문제묶음="완료"),
    ])

    summary = summarize_issue_subclasses(rows)

    assert summary["subclassified_remaining_count"] == 3
    assert sum(summary["remaining_by_subtype"].values()) == 3
    assert summary["first_execution_batch"]["subtype"] == "CONTEXT_GENERAL_REPARSE"
    assert summary["first_execution_batch"]["claim_ids"] == ["C1", "C2"]

