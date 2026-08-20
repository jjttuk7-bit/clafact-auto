# HOLD Gold Set Candidate Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Create a reproducible 250-record, stratified, human-review-ready HOLD Gold Set candidate.

**Architecture:** A pure core module groups HOLD records by pipeline reason and uses a seed per stratum for stable sampling. A small CLI writes immutable JSONL, CSV, guide, and report artifacts.

**Tech Stack:** Python 3.11 standard library, pytest.

---

### Task 1: Deterministic sampler

**Files:**
- Create: `core/hold_goldset.py`
- Test: `tests/unit/test_hold_goldset.py`

1. Test fixed-seed, per-reason quota selection.
2. Implement HOLD filtering, quota validation, and deterministic selection.
3. Run `python -m pytest tests/unit/test_hold_goldset.py -v`.

### Task 2: Review artifacts

**Files:**
- Create: `tools/create_hold_goldset.py`
- Modify: `core/hold_goldset.py`
- Test: `tests/unit/test_hold_goldset.py`

1. Test JSONL, CSV, guide, and report generation.
2. Implement an overwrite-safe writer with pending human-review fields.
3. Run the unit test and then the full suite.

### Task 3: Produce the approved sample

**Files:**
- Create: `artifacts/hold_goldset_candidate_v1_20260820/`

1. Run the CLI over `e2e_results.jsonl`.
2. Verify 1,507 inventory records, 250 sample records, and every quota.
3. Do not label pending rows as ground truth.
