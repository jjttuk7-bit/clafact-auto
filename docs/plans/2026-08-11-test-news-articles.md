# Test News Articles Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add fictional Korean news-article fixtures that can be uploaded to the Streamlit batch UI and reviewed sentence by sentence.

**Architecture:** Store the upload-ready CSV and a human-readable Markdown sentence index under `data/test_articles/`. A focused test loads the CSV with the production `load_articles` adapter and verifies the rows and companion document stay synchronized.

**Tech Stack:** Python 3.12, pytest, CSV, Markdown.

---

### Task 1: Add the fixture artifacts

**Files:**
- Create: `data/test_articles/test_news_articles.csv`
- Create: `data/test_articles/test_sentences.md`

**Step 1: Create the CSV**

Add 10 fictional rows with the production upload columns. Use only `[테스트]` titles and `example.test` URLs. Include direct-value, growth, split, unresolved-profile, ambiguous-comparison, unit, and missing-date examples.

**Step 2: Create the sentence index**

List every numerical sentence from the CSV with its purpose and safe expected final route (`AUTO 후보` or `HOLD`). Explicitly state that no fixture number is official evidence.

**Step 3: Commit**

```powershell
git add data/test_articles
git commit -m "test: add sample news article fixtures"
```

### Task 2: Verify fixture compatibility

**Files:**
- Create: `tests/unit/test_test_news_articles.py`

**Step 1: Write the failing test**

Load `test_news_articles.csv` through `core.batch_verifier.load_articles`; assert 10 valid `BatchArticle` rows, test-only URLs, and that every numeric candidate is documented by `test_sentences.md`.

**Step 2: Run test to verify it fails**

```powershell
python -m pytest tests/unit/test_test_news_articles.py -q
```

Expected: FAIL because the fixture files do not yet exist.

**Step 3: Run the focused and full suite**

```powershell
python -m pytest tests/unit/test_test_news_articles.py -q
python -m pytest -q
```

Expected: PASS.

**Step 4: Commit**

```powershell
git add tests/unit/test_test_news_articles.py
git commit -m "test: verify sample news article fixtures"
```
