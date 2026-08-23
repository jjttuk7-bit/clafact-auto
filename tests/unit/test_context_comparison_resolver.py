from core.context_comparison_resolver import resolve_context_comparison


def test_resolves_one_repeated_year_over_year_basis() -> None:
    result = resolve_context_comparison([
        ("3", "지난달 취업자는 전년 동월 대비 24만5000명 증가했다."),
        ("5", "고용률도 전년 같은 달보다 상승했다."),
    ])

    assert result is not None
    assert result.comparison_type == "YEAR_OVER_YEAR"
    assert result.sentence_ids == ("3", "5")


def test_rejects_conflicting_period_bases() -> None:
    result = resolve_context_comparison([
        ("3", "취업자는 전년 동월 대비 증가했다."),
        ("4", "실업자는 전월 대비 감소했다."),
    ])

    assert result is None


def test_returns_none_without_explicit_period_basis() -> None:
    result = resolve_context_comparison([
        ("3", "취업자는 24만5000명 증가했다."),
    ])

    assert result is None
