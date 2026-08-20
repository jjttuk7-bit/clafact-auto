# Slot Quality Validation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Validate and safely integrate the paused explicit share and dimension-slot enrichment changes, then measure their effect in a bounded official KOSIS run.

**Architecture:** Existing parser and deterministic enricher changes remain the only production scope. Tests confirm their contract; the current official batch runner performs all external calls and writes a new artifact directory without modifying the registry.

**Tech Stack:** Python 3.12, Pydantic v2, pytest, existing read-only KOSIS adapters.

---

### Task 1: Validate focused slot-enrichment changes

**Files:**
- Modify only if a focused test demonstrates a defect: `core/claim_parser.py`, `core/deterministic_slot_enricher.py`, `core/kosis_metadata_repository.py`
- Test: `tests/unit/test_claim_parser.py`, `tests/unit/test_deterministic_slot_enricher.py`, `tests/unit/test_kosis_metadata_repository.py`

1. Run the three focused test modules.
2. If a test fails, capture the failure and add the smallest regression test needed if coverage is missing.
3. Implement only the minimal correction and rerun the affected module.
4. Re-run all three focused modules.

### Task 2: Run repository regression gate

**Files:** No planned source changes.

1. Run `python -m pytest -q` from the repository root.
2. If unrelated existing failures occur, record their module and failure reason; do not mask or weaken them.
3. Inspect `git diff --check` for whitespace and patch integrity.

### Task 3: Execute bounded official verification

**Files:**
- Create: `artifacts/slot_quality_official_pilot_20260820/` (generated only)
- Run: `tools/run_official_e2e_batch.py`

1. Read the CLI help and identify required environment configuration without printing secrets.
2. Run a 25-record bounded batch with a newly named output directory.
3. Confirm the run trace records catalog, metadata, value, and publication attempt states.
4. Compare route and HOLD-reason counts to `artifacts/gold_standard_v1_official_engine_20260814_full_resilient`.

### Task 4: Commit validated source changes

**Files:** Stage only the validated parser, enrichment, metadata test/code, and planning documents; exclude unrelated artifacts and user files.

1. Review `git diff --check` and focused/full test evidence.
2. Stage explicit paths only.
3. Commit with a narrow message describing explicit share and dimension enrichment.
4. Report the bounded external-run result separately, including any API failure reasons.
