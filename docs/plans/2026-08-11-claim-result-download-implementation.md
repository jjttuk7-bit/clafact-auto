# Claim Result Download Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add in-memory JSON and XLSX downloads for a completed single-claim verification result.

**Architecture:** A pure `core/claim_result_export.py` module serializes validated `VerdictSchema` values into canonical JSON bytes and a three-sheet XLSX workbook. The Streamlit single-claim result section renders two download buttons after it constructs the verdict, with no server-side persistence.

**Tech Stack:** Python 3.12, Pydantic v2, openpyxl, Streamlit, pytest.

---

### Task 1: Export canonical verdict JSON

**Files:**
- Create: `core/claim_result_export.py`
- Create: `tests/unit/test_claim_result_export.py`

**Step 1: Write the failing test**

```python
def test_export_verdict_json_preserves_verdict_and_trace() -> None:
    payload = json.loads(export_verdict_json_bytes(verdict).decode("utf-8"))
    assert payload["verdict"] == "MATCH"
    assert payload["execution_trace"]["claim_id"] == "claim-1"
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_claim_result_export.py::test_export_verdict_json_preserves_verdict_and_trace -q`

Expected: FAIL because the exporter does not exist.

**Step 3: Write minimal implementation**

Implement `export_verdict_json_bytes(verdict)` as UTF-8 JSON from `VerdictSchema.model_dump(mode="json")`, with stable key ordering and no API response data.

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_claim_result_export.py::test_export_verdict_json_preserves_verdict_and_trace -q`

Expected: PASS.

### Task 2: Export reviewer-ready XLSX

**Files:**
- Modify: `core/claim_result_export.py`
- Modify: `tests/unit/test_claim_result_export.py`

**Step 1: Write the failing test**

```python
def test_export_verdict_xlsx_has_summary_evidence_and_trace_sheets() -> None:
    workbook = load_workbook(BytesIO(export_verdict_xlsx_bytes(verdict)))
    assert workbook.sheetnames == ["Summary", "Evidence Cells", "Execution Trace"]
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_claim_result_export.py::test_export_verdict_xlsx_has_summary_evidence_and_trace_sheets -q`

Expected: FAIL because XLSX export does not exist.

**Step 3: Write minimal implementation**

Create workbook sheets with headers; write verdict/versions to `Summary`, evidence coordinates and official values to `Evidence Cells`, and trace event fields to `Execution Trace`. Keep empty evidence or trace data as header-only sheets.

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_claim_result_export.py -q`

Expected: PASS.

### Task 3: Render the two single-claim download controls

**Files:**
- Modify: `app/streamlit_app.py`
- Modify: `tests/test_operations_panel.py`

**Step 1: Write the failing test**

```python
def test_streamlit_single_claim_result_has_json_and_xlsx_downloads() -> None:
    source = Path("app/streamlit_app.py").read_text(encoding="utf-8")
    assert "판정 결과 JSON 다운로드" in source
    assert "판정 결과 XLSX 다운로드" in source
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_operations_panel.py::test_streamlit_single_claim_result_has_json_and_xlsx_downloads -q`

Expected: FAIL because no single-claim download controls exist.

**Step 3: Write minimal implementation**

Call both exporter functions after `payload = build_review_payload(verdict)`. Render `st.download_button` controls with MIME types, descriptive labels, and filenames derived from `claim_id`. Do not add any persistent storage.

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_operations_panel.py::test_streamlit_single_claim_result_has_json_and_xlsx_downloads -q`

Expected: PASS.

### Task 4: Full verification and commit

**Files:**
- Modify: files above and both plan documents only

**Step 1: Run focused tests**

Run: `python -m pytest tests/unit/test_claim_result_export.py tests/test_operations_panel.py -q`

Expected: PASS.

**Step 2: Run full suite**

Run: `python -m pytest -q`

Expected: no failures.

**Step 3: Commit**

```bash
git add core/claim_result_export.py app/streamlit_app.py tests/unit/test_claim_result_export.py tests/test_operations_panel.py docs/plans/2026-08-11-claim-result-download-design.md docs/plans/2026-08-11-claim-result-download-implementation.md
git commit -m "feat: add claim result downloads"
```
