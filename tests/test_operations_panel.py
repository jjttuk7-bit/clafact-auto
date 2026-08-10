from pathlib import Path


def test_streamlit_app_contains_read_only_operations_artifact_panel() -> None:
    source = Path("app/streamlit_app.py").read_text(encoding="utf-8")
    assert "운영 배치 산출물 검토" in source
    assert "E2E 결과 JSONL" in source
    assert "업로드 파일은 저장하지 않습니다" in source


def test_streamlit_single_claim_result_has_json_and_xlsx_downloads() -> None:
    source = Path("app/streamlit_app.py").read_text(encoding="utf-8")

    assert "판정 결과 JSON 다운로드" in source
    assert "판정 결과 XLSX 다운로드" in source