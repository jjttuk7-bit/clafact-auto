from pathlib import Path

from core.batch_verifier import extract_batch_claim_sentences, load_articles


PROJECT_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = PROJECT_ROOT / "data" / "test_articles"


def test_test_news_csv_is_upload_ready_and_documented() -> None:
    csv_path = FIXTURE_DIR / "test_news_articles.csv"
    sentences_path = FIXTURE_DIR / "test_sentences.md"

    articles = load_articles(csv_path.name, csv_path.read_bytes())
    documented = sentences_path.read_text(encoding="utf-8")

    assert len(articles) == 10
    assert all(article.title and article.title.startswith("[테스트]") for article in articles)
    assert all(article.source_url and article.source_url.startswith("https://example.test/") for article in articles)
    assert all(sentence in documented for article in articles for sentence in extract_batch_claim_sentences(article.body))
