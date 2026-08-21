from core.explicit_numeric_slot import extract_explicit_numeric_slot

def test_extracts_direct_hectare_value() -> None:
    assert extract_explicit_numeric_slot("올해 벼 재배 면적은 67만8000ha이다.") == (678000.0, "ha", "DIRECT_VALUE")

def test_extracts_absolute_difference() -> None:
    assert extract_explicit_numeric_slot("올해 벼 재배 면적은 전년보다 2만ha 감소했다.") == (20000.0, "ha", "DIFFERENCE")

def test_extracts_growth_rate() -> None:
    assert extract_explicit_numeric_slot("전년보다 2.9% 감소했다.") == (2.9, "%", "GROWTH_RATE")