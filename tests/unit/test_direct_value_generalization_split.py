from core.direct_value_generalization_split import split_claim_rows


def _row(parent: str, child: str, indicator: str = "취업자") -> dict[str, str]:
    return {
        "원본부모Claim번호": parent,
        "자식Claim번호": child,
        "지표": indicator,
        "단위": "명",
        "주기": "월",
        "최종사유코드": "NO_EVIDENCE_COORDINATE_CANDIDATE",
    }


def test_split_is_article_level_deterministic_and_complete() -> None:
    rows = [
        _row("A00001_1", "c1"),
        _row("A00001_2", "c2"),
        _row("A00002_1", "c3"),
        _row("A00003_1", "c4"),
        _row("A00004_1", "c5"),
        _row("A00005_1", "c6"),
        _row("A00006_1", "c7"),
        _row("A00007_1", "c8"),
        _row("A00008_1", "c9"),
        _row("A00009_1", "c10"),
    ]

    first = split_claim_rows(rows, seed="clafact-type8-v1")
    second = split_claim_rows(list(reversed(rows)), seed="clafact-type8-v1")

    assert {item.claim_id: item.split_set for item in first} == {
        item.claim_id: item.split_set for item in second
    }
    article_sets: dict[str, set[str]] = {}
    for item in first:
        article_sets.setdefault(item.article_id, set()).add(item.split_set)
    assert all(len(values) == 1 for values in article_sets.values())
    assert {item.claim_id for item in first} == {f"c{i}" for i in range(1, 11)}
    assert {item.split_set for item in first} == {
        "RULE_DISCOVERY",
        "INTERMEDIATE_VALIDATION",
        "FINAL_BLIND",
    }


def test_split_rejects_duplicate_claim_identity() -> None:
    rows = [_row("A00001_1", "same"), _row("A00002_1", "same")]

    try:
        split_claim_rows(rows)
    except ValueError as error:
        assert str(error) == "DIRECT_VALUE_CLAIM_ID_NOT_UNIQUE:same"
    else:
        raise AssertionError("duplicate Claim identity was accepted")
