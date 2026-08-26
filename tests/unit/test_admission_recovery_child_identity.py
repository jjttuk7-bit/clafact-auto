from core.admission_recovery_v3 import _child_id


def test_child_id_is_unique_across_parents_with_same_sentence_and_value() -> None:
    sentence = "소비자물가지수는 116.38이다."

    first = _child_id("P1", sentence, "116.38", 1)
    second = _child_id("P2", sentence, "116.38", 1)

    assert first != second


def test_child_id_is_unique_for_repeated_expression_in_same_parent() -> None:
    sentence = "증가율은 14.2%였고 다른 품목도 14.2%였다."

    first = _child_id("P1", sentence, "14.2%", 1)
    second = _child_id("P1", sentence, "14.2%", 2)

    assert first != second
    assert first == _child_id("P1", sentence, "14.2%", 1)
