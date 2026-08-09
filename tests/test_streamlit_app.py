from streamlit.testing.v1 import AppTest


def test_streamlit_mvp_renders_and_holds_invalid_article_date() -> None:
    app = AppTest.from_file("app/streamlit_app.py")
    app.run()
    assert app.title[0].value == "CLAFACT-AUTO"
    app.text_area[0].input("2024년 전국 고용률은 70%였다.")
    app.text_input[0].input("invalid-date")
    app.button[0].click()
    app.run()
    assert any("HOLD: 기사 기준일은 YYYY-MM-DD 형식이어야 합니다." in element.value for element in app.error)
