# Deterministic Slot Enrichment Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Safely populate explicitly stated comparison, calculation, and condition slots without inferring ambiguous semantics.

**Architecture:** Add a pure rule-based extractor that recognizes only explicit Korean comparison and condition phrases. Run it before the existing structured-output enrichment; it supplies target slots when certain, while the existing provider path continues to handle unresolved values. Claims remain `HOLD` whenever the completed slots do not support a safe calculation route.

**Tech Stack:** Python 3.12+, Pydantic v2, pytest.

---

### Task 1: Specify deterministic slot rules

**Files:**
- Create: `core/deterministic_slot_enricher.py`
- Create: `tests/unit/test_deterministic_slot_enricher.py`

**Step 1: Write failing tests**

Cover explicit year-over-year, month-over-month, ratio, direct-value, seasonal-adjustment, and an ambiguous sentence that must produce no inferred slot.

**Step 2: Run the focused test**

Run: `python -m pytest tests/unit/test_deterministic_slot_enricher.py -q`
Expected: FAIL because the module does not exist.

**Step 3: Implement the minimal pure extractor**

Return only `comparison`, `calculation`, and `condition` values backed by an explicit phrase. Do not change any other ClaimSchema field.

**Step 4: Run the focused test**

Run: `python -m pytest tests/unit/test_deterministic_slot_enricher.py -q`
Expected: PASS.

### Task 2: Integrate rules before provider enrichment

**Files:**
- Modify: `core/claim_slot_enricher.py`
- Modify: `tests/unit/test_claim_slot_enricher.py`

**Step 1: Write failing integration tests**

Verify explicit rules take precedence, provider enrichment fills only remaining slots, and unresolved calculations remain `HOLD`.

**Step 2: Run focused integration tests**

Run: `python -m pytest tests/unit/test_claim_slot_enricher.py -q`
Expected: FAIL before the integration.

**Step 3: Implement the minimal integration**

Merge deterministic slots before reading provider slots and preserve existing safe-hold reason codes.

**Step 4: Run focused tests**

Run: `python -m pytest tests/unit/test_claim_slot_enricher.py -q`
Expected: PASS.

### Task 3: Verify batch safety and commit

**Files:**
- Modify: `tests/unit/test_claim_slot_enrichment_batch.py`
- Test: `tests/unit/test_deterministic_slot_enricher.py`

**Step 1: Add a batch test**

Verify an explicit rule is recorded without overwriting source claim fields and a non-AUTO record remains skipped.

**Step 2: Run verification**

Run: `python -m pytest tests/unit/test_deterministic_slot_enricher.py tests/unit/test_claim_slot_enricher.py tests/unit/test_claim_slot_enrichment_batch.py -q`
Expected: PASS.

**Step 3: Run the full suite**

Run: `python -m pytest -q`
Expected: PASS.

**Step 4: Commit**

```powershell
git add core/deterministic_slot_enricher.py core/claim_slot_enricher.py tests/unit/test_deterministic_slot_enricher.py tests/unit/test_claim_slot_enricher.py tests/unit/test_claim_slot_enrichment_batch.py docs/plans/2026-08-11-deterministic-slot-enrichment-implementation.md
git commit -m "feat: add deterministic claim slot enrichment"
```
