from core.unit_normalizer import compatible_units, convert_value


def test_converts_thousand_dollars_to_dollars() -> None:
    assert compatible_units("달러", "천달러") is True
    assert compatible_units("달러", "천불") is True
    assert compatible_units("달러", "천$") is True
    assert convert_value(127_761_371, "천달러", "달러") == 127_761_371_000
    assert convert_value(10_177_312, "천$", "달러") == 10_177_312_000