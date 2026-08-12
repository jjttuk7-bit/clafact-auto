# Export Threshold Slot Contract Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Prevent incomplete THRESHOLD Claims from entering KOSIS table selection while preserving complete threshold Claims.

**Architecture:** Extend `claim_slot_quality` with one deterministic condition validator and document the same condition fields in the Structured Output prompt. Re-run the existing ten-Claim cluster through the unchanged dynamic batch engine.

**Tech Stack:** Python 3.12+, Pydantic v2, pytest, OpenAI Structured Output prompt, dynamic KOSIS batch runner

---

### Task 1: Enforce the THRESHOLD condition contract

**Files:**
- Modify: `tests/unit/test_claim_slot_quality.py`
- Modify: `core/claim_slot_quality.py`

1. Write failing tests for missing condition, missing fields, invalid operator, invalid numeric threshold, incompatible units, and a valid predicate.
2. Run the focused tests and verify expected RED failures.
3. Implement the minimal deterministic validator.
4. Run focused tests to GREEN.

### Task 2: Align the Structured Output prompt

**Files:**
- Modify: `core/openai_function_claim_extractor.py`
- Modify: `tests/unit/test_hcx_prompt.py`

1. Require explicit threshold condition fields in a failing prompt contract test.
2. Update the parser instruction without changing the 12-slot schema.
3. Run the prompt tests.

### Task 3: Re-run and verify the ten-Claim cluster

**Files:**
- Create: `artifacts/export_threshold_contract_20260812/`

1. Freeze the ten THRESHOLD records.
2. Run the unchanged dynamic E2E batch.
3. Require all malformed records to stop at Claim Parse with explicit slot-quality detail.
4. Run all unit, integration, Goldset, and diff checks.