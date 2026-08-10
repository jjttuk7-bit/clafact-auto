# Ambiguous Comparison Review Queue Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Produce and safely apply explicit human decisions for ambiguous comparison claims.

**Architecture:** Add a pure JSONL queue builder and decision applier. Only `AMBIGUOUS_COMPARISON` records enter the queue; decisions are validated before a new result stream is produced, and unresolved records remain HOLD.

**Tech Stack:** Python, Pydantic-style registry records, pytest, JSONL.

---

### Task 1: Write failing queue and decision-validation tests

**Files:**
- Create: `tests/unit/test_ambiguous_comparison_review.py`

Write tests for filtering, approved application, rejected HOLD preservation, and invalid duplicate/unknown/incomplete decisions. Run the test and confirm failure because the module does not exist.

### Task 2: Implement deterministic review queue and applier

**Files:**
- Create: `core/ambiguous_comparison_review.py`
- Test: `tests/unit/test_ambiguous_comparison_review.py`

Implement pure functions to build review rows and apply validated decisions without generating official values. Run focused tests until green.

### Task 3: Add JSONL command-line adapter and verify

**Files:**
- Create: `tools/build_ambiguous_comparison_review_queue.py`
- Create: `tools/apply_ambiguous_comparison_decisions.py`
- Test: `tests/unit/test_ambiguous_comparison_review.py`

Add no-network file adapters, run `python -m pytest -q`, then commit all files with message `feat: add ambiguous comparison review queue`.
