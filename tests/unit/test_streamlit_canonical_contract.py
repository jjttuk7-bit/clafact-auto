from pathlib import Path


APP = Path("app/streamlit_app.py")


def test_streamlit_single_and_batch_use_the_canonical_runtime() -> None:
    source = APP.read_text(encoding="utf-8")

    assert "from core.canonical_pipeline import build_canonical_pipeline" in source
    assert "from core.canonical_batch_verifier import verify_articles_with_pipeline" in source
    assert "runtime.verify_article(" in source
    assert "verify_articles_with_pipeline(articles, runtime)" in source
    assert "BATCH_CLAIM_SPLIT_CARDINALITY" not in source
