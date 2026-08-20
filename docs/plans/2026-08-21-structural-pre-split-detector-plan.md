# Structural Pre-Split Detector Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Independent numeric assertions are safely routed to Claim split before KOSIS eligibility.

**Architecture:** Add a pure detector in `core/claim_splitter.py`, then use it as a deterministic hard guard in the admission router before eligibility. The detector only returns a routing signal; it never creates a KOSIS value, evidence coordinate, or verdict.

**Tech Stack:** Python 3.12+, regex, Pydantic, pytest.

---

### Task 1: Establish P0 regression fixtures

**Files:**
- Modify: `tests/unit/test_claim_splitter.py`
- Test: `tests/unit/test_claim_splitter.py`

**Step 1:** Write failing tests for the 16 Gold `MULTI → ELIGIBLE` error cases, represented by generalized sentence patterns.

**Step 2:** Add counterexamples: one indicator plus a comparison baseline must remain a single Claim.

**Step 3:** Run `python -m pytest tests/unit/test_claim_splitter.py -v`; expect failure because detector is absent.

### Task 2: Implement the pure structural detector

**Files:**
- Modify: `core/claim_splitter.py`
- Test: `tests/unit/test_claim_splitter.py`

**Step 1:** Add `detect_structural_multi_claim(sentence: str) -> bool`.

**Step 2:** Detect independent clause separators and parallel numeric assertion patterns; explicitly exempt a single indicator with one value and comparison phrase.

**Step 3:** Run the focused test; expect pass.

### Task 3: Connect the admission hard guard

**Files:**
- Modify: `core/claim_admission_router.py`
- Modify: `tests/unit/test_claim_admission_router.py`

**Step 1:** Write failing test that a structurally multi sentence gets `MULTI_CLAIM_SPLIT_REQUIRED` before eligibility.

**Step 2:** Route detector-positive claims to `MULTI_CLAIM_SPLIT_REQUIRED` with stable reason `STRUCTURAL_MULTI_CLAIM`.

**Step 3:** Run focused unit tests; expect pass.

### Task 4: Verify against Gold Set

**Files:**
- Use: `tools/evaluate_claim_admission_goldset.py`
- Output: `artifacts/claim_admission_structural_detector_eval_.../`

**Step 1:** Run all focused unit/integration tests.

**Step 2:** Re-run the 250 Claim Gold Set with the same no-context input contract.

**Step 3:** Compare P0 false KOSIS admissions and report any regression before permitting a 1,542-candidate run.