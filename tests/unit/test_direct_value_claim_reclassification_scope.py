from core.direct_value_claim_reclassification_scope import (
    FINAL_BLIND,
    INTERMEDIATE_VALIDATION,
    RULE_DISCOVERY,
    build_reclassification_scope,
)


def _row(claim_id: str, reason: str, split: str, source: str = "2024년 취업자는 10만명이다.") -> dict[str, str]:
    return {
        "원본부모Claim번호": claim_id,
        "자식Claim번호": claim_id,
        "개선후사유": reason,
        "사용집합": split,
        "원문": source,
        "지표": "취업자",
        "기사값": "10",
        "단위": "만명",
        "기준시점": "2024년",
        "계산방식": "DIRECT_VALUE",
    }


def test_scope_selects_only_claim_structure_reasons() -> None:
    rows = [
        _row("C1", "INDICATOR_REFINEMENT_REQUIRED", RULE_DISCOVERY),
        _row("C2", "목표 지표가 문장에 명시되지 않음", INTERMEDIATE_VALIDATION),
        _row("C3", "NO_HARD_GUARD_CANDIDATE", FINAL_BLIND),
    ]

    scope = build_reclassification_scope(rows)

    assert [item.claim_id for item in scope.records] == ["C1", "C2"]
    assert scope.reason_counts == {
        "INDICATOR_REFINEMENT_REQUIRED": 1,
        "목표 지표가 문장에 명시되지 않음": 1,
    }


def test_scope_requires_unique_claim_and_valid_split() -> None:
    duplicate = [
        _row("C1", "CLAIM_PARSE_UNCERTAIN", RULE_DISCOVERY),
        _row("C1", "MISSING_REQUIRED_SLOTS:time", INTERMEDIATE_VALIDATION),
    ]
    try:
        build_reclassification_scope(duplicate)
    except ValueError as error:
        assert str(error) == "DIRECT_VALUE_RECLASSIFICATION_CLAIM_NOT_UNIQUE:C1"
    else:
        raise AssertionError("duplicate Claim must fail")


def test_final_blind_source_is_hidden_in_audit_manifest() -> None:
    scope = build_reclassification_scope([
        _row("C1", "CLAIM_PARSE_UNCERTAIN", FINAL_BLIND, "비공개 최종 문장"),
    ])

    manifest = scope.to_audit_dict(include_final_blind_source=False)

    assert manifest["records"][0]["source_sentence"] is None
    assert manifest["split_counts"] == {FINAL_BLIND: 1}


def test_current_shape_preserves_discovery_intermediate_final_counts() -> None:
    rows = [
        *[_row(f"D{i}", "CLAIM_PARSE_UNCERTAIN", RULE_DISCOVERY) for i in range(71)],
        *[_row(f"I{i}", "TARGET_NOT_FOUND_IN_SOURCE", INTERMEDIATE_VALIDATION) for i in range(21)],
        *[_row(f"F{i}", "NON_OBSERVED_FORECAST", FINAL_BLIND) for i in range(8)],
    ]

    scope = build_reclassification_scope(rows, expected_count=100)

    assert scope.split_counts == {
        FINAL_BLIND: 8,
        INTERMEDIATE_VALIDATION: 21,
        RULE_DISCOVERY: 71,
    }
