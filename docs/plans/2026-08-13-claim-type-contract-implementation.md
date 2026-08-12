# Claim Type Contract Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enforce the canonical one-target, one-value, one-calculation Claim definition before any AUTO Claim reaches KOSIS discovery.

**Architecture:** Add a pure `assess_claim_contract` domain function returning a typed decision. Keep `ClaimSchema` load-compatible, then call the validator from both `parse_claim` and `run_dynamic_e2e_batch` so single and batch paths share one admission gate.

**Tech Stack:** Python 3.12+, Pydantic v2, pytest

---

### Task 1: Common and direct-value contract

**Files:**
- Create: `core/claim_contract.py`
- Create: `tests/unit/test_claim_contract.py`

**Step 1: Write the failing tests**

Test that non-AUTO records are preserved, complete direct values pass, missing canonical fields return ordered `MISSING_REQUIRED_SLOTS`, and unsupported calculation types HOLD.

**Step 2: Verify RED**

Run: `python -m pytest tests/unit/test_claim_contract.py -q`
Expected: FAIL because `core.claim_contract` does not exist.

**Step 3: Implement the minimal decision model and common contract**

Create immutable `ClaimContractDecision` and `assess_claim_contract`. Do not mutate the Claim.

**Step 4: Verify GREEN**

Run the same focused test and expect PASS.

### Task 2: Growth and difference contracts

**Files:**
- Modify: `core/claim_contract.py`
- Modify: `tests/unit/test_claim_contract.py`

**Steps:**

1. Add failing tests for missing/invalid comparison type, direction, percent unit, current/reference operands, and operand unit.
2. Run focused tests and confirm expected failures.
3. Implement only the tested rules using canonical fixed reason codes.
4. Run focused tests and confirm PASS.

### Task 3: Share, ratio, multiple, rank, and threshold contracts

**Files:**
- Modify: `core/claim_contract.py`
- Modify: `tests/unit/test_claim_contract.py`

**Steps:**

1. Add one valid and representative invalid test for each calculation type.
2. Confirm RED.
3. Implement explicit operand/condition checks without inference.
4. Confirm GREEN.

### Task 4: Parser admission integration

**Files:**
- Modify: `core/claim_parser.py`
- Modify: `tests/unit/test_claim_parser.py`

**Steps:**

1. Add a failing test proving an invalid `AUTO_OK` growth Claim is returned as HOLD with the contract reason.
2. Confirm RED.
3. Invoke `assess_claim_contract` after normalization/time resolution and convert a HOLD decision to an auditable Claim status.
4. Confirm parser tests pass.

### Task 5: Dynamic batch admission integration

**Files:**
- Modify: `core/dynamic_e2e_batch_runner.py`
- Modify: `tests/unit/test_dynamic_e2e_batch_runner.py`

**Steps:**

1. Add a failing test proving an imported invalid AUTO Claim holds before Catalog/KOSIS access.
2. Confirm RED.
3. Apply the same validator before Semantic Mapping and emit its stable reason/detail.
4. Confirm focused tests pass.

### Task 6: Compatibility and verification

**Files:**
- Modify: `tests/unit/test_claim_registry_loader.py`
- Modify: `docs/reference/03_DATA_SCHEMAS.md`

**Steps:**

1. Prove existing Registry records still load without source mutation.
2. Document the runtime AUTO admission contract and fixed HOLD reasons.
3. Run `python -m pytest tests/unit/test_claim_contract.py tests/unit/test_claim_parser.py tests/unit/test_dynamic_e2e_batch_runner.py -q`.
4. Run `python -m pytest -q`.
5. Review the diff for secrets, Profile dependencies, and ordering regressions.
