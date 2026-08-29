import pytest

from core.unit_normalizer import compatible_units, convert_value


def test_million_dollars_is_a_supported_usd_scale() -> None:
    assert compatible_units("달러", "백만달러") is True
    assert convert_value(1_890_000_000, "달러", "백만달러") == pytest.approx(1_890)
