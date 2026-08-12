# Export Rank Slot Contract Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Route malformed export RANK Claims to explicit parser HOLDs and preserve only complete single-target rank contracts.

**Architecture:** Add a pure rank-contract validator to the existing `claim_slot_quality` boundary, align the OpenAI prompt, and re-run the eight-record cluster through the unchanged batch engine.

**Tech Stack:** Python 3.12+, Pydantic v2, pytest, OpenAI Structured Output prompt

---

### Task 1: Add the RANK slot contract

**Files:**
- Modify: `tests/unit/test_claim_slot_quality.py`
- Modify: `core/claim_slot_quality.py`

1. Add failing tests for non-rank unit, non-integer rank, multiple targets, missing condition fields, invalid order, rank mismatch, and a valid Claim.
2. Verify RED failures.
3. Implement the minimal validator using normalized dimensions.
4. Verify GREEN.

### Task 2: Align OpenAI Structured Output instructions

**Files:**
- Modify: `tests/unit/test_openai_function_claim_extractor.py`
- Modify: `core/openai_function_claim_extractor.py`

1. Add a failing prompt contract test.
2. Document `rank_value`, `order`, and `population_scope` while keeping instructions concise.
3. Verify prompt tests.

### Task 3: Re-run eight Claims and full export subset

**Files:**
- Create: `artifacts/export_rank_contract_20260812/`

1. Freeze the eight RANK records.
2. Re-run them through the dynamic batch.
3. Re-run all 62 export records.
4. Run all unit, integration, Goldset, and diff checks.