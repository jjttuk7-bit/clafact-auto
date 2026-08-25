from pathlib import Path


APP_PATH = Path(__file__).resolve().parents[2] / "app" / "streamlit_app.py"


def test_streamlit_uses_dynamic_official_source_presentation() -> None:
    source = APP_PATH.read_text(encoding="utf-8")

    assert "build_official_source_presentation" in source
    assert "source_presentation.value_label" in source
    assert "source_presentation.evidence_label" in source
    assert "source_presentation.provenance_rows" in source
    assert 'metric("KOSIS 공식값"' not in source
