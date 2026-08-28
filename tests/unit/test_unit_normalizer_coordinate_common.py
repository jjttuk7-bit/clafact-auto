import pytest

from core.unit_normalizer import compatible_units, convert_value


@pytest.mark.parametrize(
    ("left", "right"),
    [
        ("원", "백만원"),
        ("조원", "억원"),
        ("달러", "억달러"),
        ("만달러", "천달러"),
        ("명", "만명"),
        ("가구", "천가구"),
        ("곳", "개"),
    ],
)
def test_compatible_units_supports_safe_same_measure_scales(left: str, right: str) -> None:
    assert compatible_units(left, right) is True


def test_convert_value_uses_deterministic_currency_scale() -> None:
    assert convert_value(1.2, "조원", "억원") == pytest.approx(12_000)
    assert convert_value(708, "억달러", "천달러") == pytest.approx(70_800_000)


@pytest.mark.parametrize(
    ("left", "right"),
    [
        ("원", "달러"),
        ("%", "%포인트"),
        ("명", "가구"),
        ("대", "개"),
    ],
)
def test_compatible_units_rejects_different_measure_families(left: str, right: str) -> None:
    assert compatible_units(left, right) is False
