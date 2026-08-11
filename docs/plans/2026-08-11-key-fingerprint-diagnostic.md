# Key Fingerprint Diagnostic Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Safely show which process configuration is in use without revealing an OpenAI API key.

**Architecture:** A small shared utility turns an optional secret into `미설정` or `설정됨 (SHA-256: first 12 hex characters)`. Streamlit renders the utility output under the OpenAI connection state; callers may use the same utility in batch diagnostics without recording the secret.

**Tech Stack:** Python 3.12, hashlib, Streamlit, pytest.

---

### Task 1: Secret-safe fingerprint helper

**Files:**
- Create: `core/secret_fingerprint.py`
- Create: `tests/unit/test_secret_fingerprint.py`

**Step 1:** Write tests for missing keys and stable SHA-256 prefixes, asserting the raw secret is not returned.

**Step 2:** Run the new test and confirm import failure.

**Step 3:** Implement `describe_secret_fingerprint(value)` with no logging or persistence.

**Step 4:** Run the new test and confirm it passes.

### Task 2: Streamlit diagnostic rendering

**Files:**
- Modify: `app/streamlit_app.py`
- Modify: `tests/test_streamlit_app.py`

**Step 1:** Add a failing AppTest asserting OpenAI mode renders the fingerprint diagnostic but never raw key content.

**Step 2:** Run the test and confirm it fails.

**Step 3:** Render a caption below the connection status using the shared helper.

**Step 4:** Run focused tests and the complete suite.

### Task 3: Verify and commit

**Files:**
- Modify: `docs/plans/2026-08-11-key-fingerprint-diagnostic.md`

**Step 1:** Run `python -m pytest -q`.

**Step 2:** Inspect diff and secret-leak guard assertions.

**Step 3:** Commit the diagnostic and tests.