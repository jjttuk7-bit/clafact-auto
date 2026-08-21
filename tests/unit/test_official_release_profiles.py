from core.kosis_publication import _press_release_board_id, _press_release_queries


def test_birth_survey_uses_registered_kostat_release_profile() -> None:
    assert _press_release_board_id("인구동향조사") == "213"
    assert _press_release_queries("인구동향조사", "2024-12") == [
        "2024년 12월 인구동향"
    ]


def test_cpi_survey_uses_registered_kostat_release_profile() -> None:
    assert _press_release_board_id("소비자물가조사") == "213"
    assert _press_release_queries("소비자물가조사", "2025-10") == [
        "2025년 10월 소비자물가동향"
    ]
