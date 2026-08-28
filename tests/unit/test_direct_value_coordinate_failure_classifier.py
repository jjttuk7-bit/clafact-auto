from core.direct_value_coordinate_failure_classifier import classify_coordinate_failure


def _claim(**updates: object) -> dict[str, object]:
    value: dict[str, object] = {
        "source_sentence": "2024년 총인구는 100만명이다.",
        "indicator": "총인구",
        "unit": "명",
        "time": "2024",
        "frequency": "년",
        "region": "전국",
        "population": None,
        "dimension": None,
    }
    value.update(updates)
    return value


def _candidate(**updates: object) -> dict[str, object]:
    value: dict[str, object] = {
        "tbl_id": "T1",
        "tbl_name": "총인구",
        "core_item_names": ["총인구"],
        "unit_names": ["천명"],
        "frequency": "년",
        "dimension_names": ["지역별"],
        "dimension_members": {"R": ["전국"]},
        "metadata_status": "OFFICIAL_METADATA_READY",
    }
    value.update(updates)
    return value


def test_indicator_unit_role_error_precedes_coordinate_causes() -> None:
    result = classify_coordinate_failure(
        _claim(
            source_sentence="회사는 토지를 1813억원에 매입했다.",
            indicator="총인구",
            unit="원",
        ),
        {"hard_guard_best_reject_UNIT_CONFLICT": 1},
        [_candidate(unit_names=["천명"])],
    )

    assert result.primary_cause == "CLAIM_STRUCTURE_ERROR"
    assert "INDICATOR_UNIT_MEASURE_MISMATCH" in result.evidence_codes


def test_same_currency_scale_is_a_unit_coordinate_gap() -> None:
    result = classify_coordinate_failure(
        _claim(indicator="수입액", unit="원"),
        {"hard_guard_best_reject_UNIT_CONFLICT": 1},
        [_candidate(core_item_names=["수입액"], unit_names=["억원"])],
    )

    assert result.primary_cause == "UNIT_COORDINATE_GAP"
    assert result.rule_family == "SAME_MEASURE_UNIT_SCALE"


def test_different_currencies_are_not_a_scale_gap() -> None:
    result = classify_coordinate_failure(
        _claim(indicator="수출액", unit="원"),
        {"hard_guard_best_reject_UNIT_CONFLICT": 1},
        [_candidate(core_item_names=["수출액"], unit_names=["천달러"])],
    )

    assert result.primary_cause == "SEMANTIC_COORDINATE_AMBIGUITY"
    assert "CROSS_CURRENCY_NOT_AUTOMATIC" in result.evidence_codes


def test_best_reject_code_selects_period_region_dimension_and_metadata_causes() -> None:
    period = classify_coordinate_failure(
        _claim(), {"hard_guard_best_reject_FREQUENCY_CONFLICT": 2}, [_candidate()]
    )
    region = classify_coordinate_failure(
        _claim(region="경기"), {"hard_guard_best_reject_REGION_GRANULARITY_CONFLICT": 1}, [_candidate()]
    )
    dimension = classify_coordinate_failure(
        _claim(dimension={"product": "라면"}),
        {"hard_guard_best_reject_DIMENSION_MEMBER_CONFLICT": 1},
        [_candidate()],
    )
    metadata = classify_coordinate_failure(
        _claim(), {"hard_guard_best_reject_METADATA_INCOMPLETE": 1}, [_candidate()]
    )

    assert period.primary_cause == "PERIOD_FREQUENCY_GAP"
    assert region.primary_cause == "REGION_COORDINATE_GAP"
    assert dimension.primary_cause == "DIMENSION_COORDINATE_GAP"
    assert metadata.primary_cause == "METADATA_GAP"


def test_classifier_records_supporting_causes_and_does_not_use_claim_id() -> None:
    diagnostics = {
        "hard_guard_best_reject_UNIT_CONFLICT": 1,
        "hard_guard_best_reject_TIME_NOT_AVAILABLE": 1,
    }
    first = classify_coordinate_failure(_claim(claim_id="C1"), diagnostics, [_candidate()])
    second = classify_coordinate_failure(_claim(claim_id="C2"), diagnostics, [_candidate()])

    assert first == second
    assert first.primary_cause == "PERIOD_FREQUENCY_GAP"
    assert "UNIT_CONFLICT" in first.supporting_causes
    assert first.evidence_codes
