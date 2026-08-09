import pytest

from core.ui_labels import translate_status


@pytest.mark.parametrize(
    ("raw_status", "expected_label"),
    [
        ("AUTO_OK", "자동 처리 가능"),
        ("HOLD", "보류"),
        ("HUMAN_REVIEW", "사람 검토 필요"),
        ("MATCH", "일치"),
        ("MISMATCH", "불일치"),
        ("UNDETERMINED", "판정 보류"),
        ("AUTO", "자동"),
    ],
)

def test_translate_status_returns_korean_label_for_user_facing_status(raw_status: str, expected_label: str) -> None:
    assert translate_status(raw_status) == expected_label
