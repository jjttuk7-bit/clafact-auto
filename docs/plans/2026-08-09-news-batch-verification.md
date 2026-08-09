# News Batch Verification Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add session-only CSV/XLSX/JSON batch validation for crawled news articles and an auditable XLSX result download.

**Architecture:** A new core batch module converts uploaded tabular rows into article contracts, splits numerical text into claim sentences, and invokes an injected verifier for each claim. The Streamlit page uses the current single-claim pipeline through that interface and exposes a compact batch upload/result area; raw uploads are never persisted.

**Tech Stack:** Python 3.12, Pydantic v2, standard-library CSV/JSON, openpyxl, Streamlit, pytest.

---

### Task 1: Define batch article/result contracts and input validation

**Files:**
- Create: `core/batch_verifier.py`
- Test: `tests/unit/test_batch_verifier.py`

**Step 1: Write the failing test**

```python
def test_load_articles_requires_article_id_published_at_and_body() -> None:
    with pytest.raises(ValueError, match="BATCH_REQUIRED_COLUMNS"):
        load_articles_csv(b"article_id,body\\nA1,text\\n")
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_batch_verifier.py -q`
Expected: FAIL because `core.batch_verifier` does not exist.

**Step 3: Write minimal implementation**

Implement article contracts and CSV/JSON/XLSX decoding. Require `article_id`, `published_at`, and `body`; preserve optional `title` and `source_url`. Parse dates strictly and do not write uploaded bytes to disk.

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_batch_verifier.py -q`
Expected: PASS.

### Task 2: Split articles and retain a Claim-level audit row

**Files:**
- Modify: `core/batch_verifier.py`
- Modify: `tests/unit/test_batch_verifier.py`

**Step 1: Write the failing test**

```python
def test_batch_splits_numeric_article_sentences_and_keeps_article_context() -> None:
    result = verify_articles([article], verifier)
    assert [row.source_sentence for row in result.claim_rows] == ["2025년 3월 취업자 수는 2858만9000명이었다."]
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_batch_verifier.py -q`
Expected: FAIL because `verify_articles` does not exist.

**Step 3: Write minimal implementation**

Use deterministic sentence segmentation and `split_complex_claim()`. Invoke the supplied verifier once per split Claim; convert per-row exceptions into `HOLD` records so one bad article cannot interrupt the batch.

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_batch_verifier.py -q`
Expected: PASS.

### Task 3: Export results as a review-ready XLSX workbook

**Files:**
- Modify: `core/batch_verifier.py`
- Modify: `tests/unit/test_batch_verifier.py`

**Step 1: Write the failing test**

```python
def test_export_creates_claim_article_and_review_sheets() -> None:
    workbook = load_workbook(BytesIO(export_batch_xlsx(result)))
    assert workbook.sheetnames == ["Claim Results", "Article Summary", "Review Queue"]
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_batch_verifier.py -q`
Expected: FAIL because no exporter exists.

**Step 3: Write minimal implementation**

Create an in-memory XLSX with stable column headers, frozen header rows, and three sheets. Include the KOSIS coordinate and official/calculated values. `Review Queue` contains only HOLD/HUMAN_REVIEW rows and their console payload fields.

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_batch_verifier.py -q`
Expected: PASS.

### Task 4: Add Streamlit upload, summary, and download controls

**Files:**
- Modify: `app/streamlit_app.py`
- Modify: `tests/test_streamlit_app.py`

**Step 1: Write the failing test**

```python
def test_streamlit_mvp_renders_batch_upload_control() -> None:
    app = AppTest.from_file("app/streamlit_app.py")
    app.run()
    assert app.file_uploader[0].label == "크롤링 뉴스 파일 업로드"
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_streamlit_app.py -q`
Expected: FAIL because the upload control is absent.

**Step 3: Write minimal implementation**

Add a separate batch section, accept CSV/XLSX/JSON, run only on an explicit button click, display verdict totals and result table, and provide `st.download_button`. Keep the existing single-sentence controls unchanged.

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_streamlit_app.py -q`
Expected: PASS.

### Task 5: Full verification and deployment

**Files:**
- Modify: relevant files above only

**Step 1: Run focused tests**

Run: `python -m pytest tests/unit/test_batch_verifier.py tests/test_streamlit_app.py -q`
Expected: PASS.

**Step 2: Run full suite**

Run: `python -m pytest -q`
Expected: no failures.

**Step 3: Commit and push**

```bash
git add core/batch_verifier.py app/streamlit_app.py tests/unit/test_batch_verifier.py tests/test_streamlit_app.py docs/plans/2026-08-09-news-batch-verification.md
git commit -m "feat: add crawled news batch verification"
git push origin main
```
