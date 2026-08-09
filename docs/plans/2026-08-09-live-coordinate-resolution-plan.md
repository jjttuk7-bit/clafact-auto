# Live Coordinate Resolution Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Verify one unambiguous CPI detailed-item year-on-year claim from an uploaded article using two official KOSIS evidence cells.

**Architecture:** Registered official coordinate data remains the confirmation authority. A resolver creates current and prior-year cells from an explicit item profile, then the existing fetcher and calculator produce the growth rate. Multi-value sentences remain HOLD to preserve the present batch-row contract.

**Tech Stack:** Python 3.11+, Pydantic v2, pytest, KOSIS read-only API adapter.

---

### Task 1: Add an explicit CPI growth coordinate resolver

**Files:**
- Create: `core/cpi_growth_resolver.py`
- Test: `tests/unit/test_cpi_growth_resolver.py`

**Step 1:** Write a failing test for a unique detailed CPI item that expects current/prior cells and `GROWTH_RATE`.

**Step 2:** Run `python -m pytest tests/unit/test_cpi_growth_resolver.py -q` and confirm collection/test failure.

**Step 3:** Implement a minimal resolver that only accepts registered item aliases, a monthly article period, and exactly one numeric claim.

**Step 4:** Rerun the test and confirm pass.

### Task 2: Execute growth calculation in the verification pipeline

**Files:**
- Modify: `app/streamlit_app.py`
- Test: `tests/unit/test_cpi_growth_resolver.py`

**Step 1:** Write a failing pipeline-helper test proving two values are passed to `calculate(GROWTH_RATE)`.

**Step 2:** Implement a narrow helper that uses existing `OfficialValueFetcher` and `CalculationPlan`.

**Step 3:** Rerun focused tests.

### Task 3: Preserve review handling for compound sentences

**Files:**
- Modify: `core/cpi_growth_resolver.py`
- Test: `tests/unit/test_cpi_growth_resolver.py`

**Step 1:** Write a failing test for a sentence with multiple item/value pairs.

**Step 2:** Return no coordinate plan for that sentence.

**Step 3:** Run focused tests, full `python -m pytest -q`, `python -m compileall -q app core schemas`, and `git diff --check`.

### Task 4: Commit and push

**Files:**
- Add plan and implementation/test files.

**Step 1:** Review `git diff`.

**Step 2:** Commit the verified changes and push `main`.
