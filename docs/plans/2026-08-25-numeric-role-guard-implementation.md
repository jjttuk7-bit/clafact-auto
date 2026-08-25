# Numeric Role Guard Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Prevent age-group and duration expressions from being accepted as the target statistic in all canonical pipeline entrypoints.

**Architecture:** Add one deterministic numeric-role guard in `core`, call it from both fresh Structured Output parsing and persisted Claim recovery, and prove the Streamlit-shared canonical path stops before official lookup. The guard fails closed without inventing a replacement value.

**Tech Stack:** Python 3.14 runtime, Pydantic v2, pytest, Streamlit canonical runtime adapter.

---

### Task 1: Add failing Core role tests

**Files:**
- Modify: `tests/unit/test_claim_parser.py`
- Modify: `tests/unit/test_validated_claim_recovery.py`

**Steps:**
1. Add a parser test where `20대` is incorrectly returned as value `20`, unit `대`.
2. Add a positive parser test where `자동차 100대` remains valid.
3. Add a persisted Claim test for the same age-role conflict.
4. Run the three tests and confirm the conflict tests fail before implementation.

### Task 2: Implement the deterministic guard

**Files:**
- Create: `core/numeric_role_guard.py`
- Modify: `core/claim_parser.py`
- Modify: `core/validated_claim_recovery.py`

**Steps:**
1. Classify matching age-group and duration spans from source text.
2. Return stable reason codes for role conflicts.
3. Apply the guard before Claim contract admission in both entrypoints.
4. Run focused tests and confirm all pass.

### Task 3: Prove dashboard-path enforcement

**Files:**
- Modify: `tests/unit/test_unified_claim_pipeline.py`

**Steps:**
1. Add a canonical article test with a bad LLM extraction.
2. Assert the entry is held at Claim parsing and the official service receives no Claim.
3. Run the dashboard/canonical focused tests.

### Task 4: Verify and deliver

**Files:**
- No production changes.

**Steps:**
1. Run relevant unit and Streamlit-path tests.
2. Run the full suite and compare failures with the recorded baseline of 8.
3. Inspect the diff and run `git diff --check`.
4. Commit only this feature and its documentation.
5. Push the verified commit to `origin/main` as explicitly authorized.
