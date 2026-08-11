from core.comparison_normalizer import normalize_comparison


def test_normalizes_period_alias_to_basis_and_preserves_direction() -> None:
    result = normalize_comparison({"period": "전년 동월 대비", "direction": "하락"})

    assert result == {"basis": "전년 동월 대비", "direction": "하락"}
