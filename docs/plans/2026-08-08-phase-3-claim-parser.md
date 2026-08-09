# PHASE 3 Claim Parser Implementation Plan

> **For Codex:** REQUIRED SUB-SKILL: Use test-driven development to implement this plan task-by-task.

**Goal:** Convert one news sentence into a validated 12-slot `ClaimSchema` through a structured-output adapter, splitting multi-claim sentences before parsing.

**Architecture:** `split_complex_claim()` is deterministic and only divides clauses with multiple numeric values. `parse_claim()` accepts a typed extractor protocol—not a free-text response—and validates AUTO eligibility before returning a `ClaimSchema`; ambiguous or incomplete interpretation is routed to HOLD/HUMAN_REVIEW.

**Tech Stack:** Python 3.12+, Pydantic v2, pytest.

---

### Task 1: Claim splitting

**Files:**
- Create: `core/claim_splitter.py`
- Test: `tests/unit/test_claim_splitter.py`

1. Write tests for single claims, Korean connectors, comma-delimited repeated claims, and punctuation preservation.
2. Run the focused test and observe import failure.
3. Implement the smallest deterministic splitter.
4. Run the focused test.

### Task 2: Structured parser adapter

**Files:**
- Create: `core/claim_parser.py`
- Test: `tests/unit/test_claim_parser.py`

1. Write at least ten tests covering typed extraction, stable IDs, source preservation, AUTO_OK, missing slots, explicit HOLD/HUMAN_REVIEW, invalid input, and extractor contract failures.
2. Run the focused test and observe import failure.
3. Implement protocol-based parsing and AUTO eligibility validation without any free-text intermediate contract.
4. Run focused and full tests.

