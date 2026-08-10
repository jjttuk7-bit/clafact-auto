# KOSIS Evidence Snapshot Service Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build audited KOSIS evidence coordinates from exact verification profiles and preserve article-date-aware snapshot metadata without generating any official value.

**Architecture:** Extend the typed verification profile with profile-owned frequency and unit. Add a pure service that accepts an `AUTO_OK` claim, one profile, and a resolved period, returning `CONFIRMED` with an `EvidenceCellSchema` or `HOLD` with a stable reason. Extend the existing snapshot writer with optional article-date metadata while retaining response hashing and secret filtering. Official-value lookup remains in `OfficialValueFetcher`.

**Tech Stack:** Python 3.12+, Pydantic v2, pytest, standard-library JSON and SHA-256.

---

### Task 1: Add profile-owned evidence metadata

**Files:**
- Modify: `schemas/verification_profile.py`
- Modify: `tests/unit/test_verification_profile_loader.py`

**Step 1: Write the failing tests**

Add `prd_se` and `unit` to the valid profile fixture. Add one schema test that removes either field and expects validation failure.

**Step 2: Run the focused tests**

Run: `python -m pytest tests/unit/test_verification_profile_loader.py -q`

Expected: FAIL because the profile does not require both retrieval metadata fields.

**Step 3: Implement the minimal schema fields**

Add non-empty `prd_se` and `unit` fields to `VerificationProfileSchema`.

**Step 4: Run the focused tests**

Run: `python -m pytest tests/unit/test_verification_profile_loader.py -q`

Expected: PASS.

### Task 2: Define evidence resolution tests

**Files:**
- Create: `tests/unit/test_verification_evidence_service.py`

**Step 1: Write failing tests**

Test a confirmed cell from an exact profile plus explicit period, a missing-period HOLD, unit mismatch HOLD, frequency mismatch HOLD, and non-`AUTO_OK` claim HOLD.

**Step 2: Run the focused tests**

Run: `python -m pytest tests/unit/test_verification_evidence_service.py -q`

Expected: FAIL because the service module is missing.

### Task 3: Implement the deterministic profile-to-evidence service

**Files:**
- Create: `core/verification_evidence_service.py`
- Test: `tests/unit/test_verification_evidence_service.py`

**Step 1: Implement minimal public API**

```python
def resolve_profile_evidence(claim, profile, period) -> EvidenceResolution:
    ...
```

Return only `CONFIRMED` with a complete `EvidenceCellSchema`, or `HOLD` with one of `CLAIM_NOT_AUTO_OK`, `EVIDENCE_PERIOD_MISSING`, `EVIDENCE_UNIT_MISMATCH`, `EVIDENCE_FREQUENCY_MISMATCH`, or `PROFILE_COORDINATE_INCOMPLETE`.

**Step 2: Run focused tests**

Run: `python -m pytest tests/unit/test_verification_evidence_service.py -q`

Expected: PASS.

### Task 4: Preserve snapshot audit metadata

**Files:**
- Modify: `core/snapshot_store.py`
- Modify: `tests/unit/test_snapshot_store.py`

**Step 1: Write a failing test**

Save a snapshot with an article date and assert that request coordinates, article date, retrieval time, and response hash are present while an API key is absent.

**Step 2: Run focused tests**

Run: `python -m pytest tests/unit/test_snapshot_store.py -q`

Expected: FAIL because article-date metadata is not accepted or persisted.

**Step 3: Implement the minimal extension**

Accept an optional article date and remove known API-key fields from saved request parameters before writing JSON.

**Step 4: Run focused tests**

Run: `python -m pytest tests/unit/test_snapshot_store.py -q`

Expected: PASS.

### Task 5: Verify and commit

**Files:**
- Modify: `schemas/verification_profile.py`
- Create: `core/verification_evidence_service.py`
- Modify: `core/snapshot_store.py`
- Modify: relevant unit tests
- Create: `docs/plans/2026-08-11-evidence-snapshot-service-implementation.md`

**Step 1: Run full test suite**

Run: `python -m pytest -q`

Expected: all tests pass.

**Step 2: Commit**

```bash
git add schemas/verification_profile.py core/verification_evidence_service.py core/snapshot_store.py tests/unit/test_verification_profile_loader.py tests/unit/test_verification_evidence_service.py tests/unit/test_snapshot_store.py docs/plans/2026-08-11-evidence-snapshot-service-implementation.md
git commit -m "feat: add evidence snapshot service"
```
