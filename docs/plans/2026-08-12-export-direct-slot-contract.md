# Export Direct-Value Slot Contract Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Prevent non-monetary and wrong-target Claims parsed as direct export amounts from entering KOSIS catalog selection.

**Architecture:** Extend the existing deterministic `claim_slot_quality` boundary rather than adding a new pipeline stage. The gate validates the semantic contract among indicator, calculation, unit, source sentence, and dimension; valid monetary product-export Claims continue through the existing Concept → Catalog → Guard → Evidence flow.

**Tech Stack:** Python 3.12+, Pydantic v2, pytest, existing dynamic KOSIS batch runner

---

### Task 1: Enforce direct export amount/unit compatibility

**Files:**
- Modify: `core/claim_slot_quality.py`
- Modify: `tests/unit/test_claim_slot_quality.py`

1. Add a failing test for `indicator=수출액`, `calculation=DIRECT_VALUE`, and units `%`, `%p`, `대`, or `개`.
2. Verify the test fails because these Claims currently pass.
3. Add a deterministic currency-unit predicate covering 원·달러 scale forms.
4. Return `CLAIM_PARSE_UNCERTAIN` with the detected mismatch before catalog search.
5. Add a positive test showing a 화장품 수출액/달러 Claim remains eligible.

### Task 2: Verify the 19-Claim cluster through the unchanged batch engine

**Files:**
- Create: `artifacts/export_direct_slot_contract_20260812/`

1. Freeze the 19 remaining `DIRECT_VALUE + NO_HARD_GUARD_CANDIDATE` records as a test input artifact.
2. Run them with the existing semantic standard and KOSIS discovery snapshot.
3. Confirm non-monetary direct export Claims stop at `CLAIM_PARSE`.
4. Confirm the valid cosmetics monetary Claim reaches catalog/guard processing.
5. Run unit, integration, Goldset, and `git diff --check` verification.