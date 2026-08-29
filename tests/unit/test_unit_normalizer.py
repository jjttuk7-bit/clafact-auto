from core.unit_normalizer import compatible_units, convert_value


def test_converts_thousand_dollars_to_dollars() -> None:
    assert compatible_units("달러", "천달러") is True
    assert compatible_units("달러", "천불") is True
    assert compatible_units("달러", "천$") is True
    assert convert_value(127_761_371, "천달러", "달러") == 127_761_371_000
    assert convert_value(10_177_312, "천$", "달러") == 10_177_312_000

def test_converts_official_thousand_people_to_article_ten_thousand_people() -> None:
    assert compatible_units("만 명", "천명") is True
    assert compatible_units("만명", "명") is True
    assert convert_value(2_390, "천명", "만 명") == 239


def test_generic_index_unit_matches_one_official_basis() -> None:
    assert compatible_units("지수", "2020=100") is True
    assert compatible_units("지수", "지수(2020년=100)") is True
    assert compatible_units("지수(2015년=100)", "지수(2020년=100)") is False