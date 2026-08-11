# Test News Articles Design

## Purpose

Provide deterministic Korean sample news material for exercising the Streamlit article-upload path without changing the approved 1,531-Claim internal-validation corpus.

## Artifacts

- `data/test_articles/test_news_articles.csv`: upload-ready article rows with `article_id`, `published_at`, `title`, `body`, and `source_url`.
- `data/test_articles/test_sentences.md`: every numerical sentence, its intent, and the safe expected final route.

## Coverage

The fixture contains 10 fictional, clearly labelled test articles. It covers a direct official-value candidate, year-over-year growth, a multi-Claim sentence, an unresolved Profile, an ambiguous comparison, a missing-date validation example, a unit conversion case, and a KOSIS coordinate hold. It never presents fictional numbers as real reporting or as KOSIS evidence.

## Safety and Validation

All rows use `https://example.test/` URLs and titles beginning with `[테스트]`. Expected outcomes are route expectations, not asserted official values: an `AUTO` result requires the currently configured official Profile and article-time evidence; otherwise the correct result is `HOLD`. A unit test will load the CSV through `load_articles` and verify every numerical sentence is represented in the companion Markdown index.
