# Claim Slot Quality Gate Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Block malformed 12-slot Claims before KOSIS discovery and emit a deterministic reparse queue without changing imported Gold records.

**Architecture:** Introduce a pure `core.claim_slot_quality` classifier that detects a source-specific inflation modifier missing from the parsed indicator. Call it in `run_dynamic_e2e_batch` immediately after the existing parse-status check. The batch output uses `CLAIM_PARSE_UNCERTAIN` and includes a quality-detail payload for downstream reparse queue generation.

**Tech Stack:** Python 3.12, Pydantic v2, pytest.

---

### Task 1: Define the pure quality classifier

**Files:**
- Create: `core/claim_slot_quality.py`
- Test: `tests/unit/test_claim_slot_quality.py`

**Step 1:** Write a failing test for “가공식품 물가” parsed as `물가상승률`; expect `CLAIM_PARSE_UNCERTAIN` and modifier `가공식품`.

**Step 2:** Run the new test and confirm it fails because the module does not exist.

**Step 3:** Implement the minimal typed decision model and deterministic matching for the explicit inflation modifiers.

**Step 4:** Re-run the test; expect PASS.

### Task 2: Keep valid generic inflation claims eligible

**Files:**
- Modify: `tests/unit/test_claim_slot_quality.py`

**Step 1:** Write a failing test for a generic national “물가 상승률” sentence with the same indicator; expect PASS.

**Step 2:** Run it and verify the intended failure.

**Step 3:** Narrow classifier matching to source modifiers absent from the indicator.

**Step 4:** Run the unit file; expect PASS.

### Task 3: Integrate before semantic mapping

**Files:**
- Modify: `core/dynamic_e2e_batch_runner.py`
- Modify: `tests/unit/test_dynamic_e2e_batch_runner.py`

**Step 1:** Write a failing dynamic-batch test asserting malformed input holds at `CLAIM_PARSE` with `CLAIM_PARSE_UNCERTAIN`, before a live catalog adapter can be called.

**Step 2:** Run the test and confirm it fails.

**Step 3:** Add the quality gate after parse-status/date validation and append quality detail to the result.

**Step 4:** Run relevant unit tests; expect PASS.

### Task 4: Create deterministic reparse queue artifact

**Files:**
- Create: `core/claim_slot_quality_queue.py`
- Create: `tests/unit/test_claim_slot_quality_queue.py`

**Step 1:** Write a failing test that converts a quality-held batch result into a queue row with claim ID, source sentence, reason, and modifier.

**Step 2:** Implement the minimal queue builder without modifying source Registry.

**Step 3:** Run queue tests; expect PASS.

### Task 5: Verify first bottleneck cluster

**Files:**
- Create: `artifacts/gate2_inflation_slot_quality_20260812/`

**Step 1:** Run the 38-record registry through the frozen snapshot.

**Step 2:** Confirm source-specific cases are quality-held and generic cases retain normal KOSIS routing.

**Step 3:** Run snapshot, dynamic-batch, quality-classifier, and queue test files; expect all PASS.
