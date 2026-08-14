# Multi-Claim Input UI Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Let a Streamlit user submit a sentence or article body, review every split Claim in a
summary, and select one persisted Claim for its independent evidence detail.

**Architecture:** Keep article parsing and official resolution in the existing button-triggered
execution block, save a serializable result object in `st.session_state`, and render the summary
and selected detail from that state on every rerun.  The Core Article → Claim Split → 12-slot
pipeline remains unchanged.

**Tech Stack:** Python 3.12+, Streamlit, Pydantic v2, pytest.

---

### Task 1: Add a failing UI contract test

**Files:**
- Modify: `tests/test_streamlit_app.py`

**Step 1: Write the failing test**

Add an AppTest case with an article producing two parsed Claims.  Assert the UI contains the
label `검증할 뉴스 문장 또는 기사 본문`, a two-row Claim summary, and a Claim selector.

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_streamlit_app.py -k multi_claim -q`

Expected: FAIL because current UI calls the input `검증할 뉴스 문장` and has no results summary.

### Task 2: Persist an article verification run

**Files:**
- Modify: `app/streamlit_app.py`
- Test: `tests/test_streamlit_app.py`

**Step 1: Write the failing test**

After the initial simulated button run, change the selector and assert the selected Claim's
detail remains visible without invoking parsing a second time.

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_streamlit_app.py -k multi_claim -q`

Expected: FAIL because the current results exist only during the button-triggered rerun.

**Step 3: Write minimal implementation**

Store the claims, per-Claim resolutions, and provider label in `st.session_state` after a
successful execution.  Render the summary table and selected detail from the stored run.

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_streamlit_app.py -k multi_claim -q`

Expected: PASS.

### Task 3: Run targeted regression tests

**Files:**
- Test: `tests/test_streamlit_app.py`
- Test: `tests/unit/test_claim_splitter.py`
- Test: `tests/unit/test_article_claim_pipeline.py`

**Step 1: Run the focused suite**

Run: `python -m pytest tests/test_streamlit_app.py tests/unit/test_claim_splitter.py tests/unit/test_article_claim_pipeline.py -q`

Expected: PASS, or report unrelated pre-existing failures separately.

### Task 4: Commit the isolated change

**Files:**
- Modify: `app/streamlit_app.py`, `tests/test_streamlit_app.py`
- Create: `docs/plans/2026-08-14-multi-claim-ui-design.md`, `docs/plans/2026-08-14-multi-claim-ui-implementation.md`

**Step 1: Inspect and commit**

Run: `git status --short && git diff --check`

Commit: `git commit -m "feat: show and persist split article claims"`
