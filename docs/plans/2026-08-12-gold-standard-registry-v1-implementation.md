# Gold Standard Registry v1 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the supplied 1,542-row 12-slot XLSX the immutable canonical Registry used by the dynamic KOSIS E2E batch and available for operator inspection.

**Architecture:** Extend the existing Registry importer so it preserves all ClaimSchema slots, including JSON-formatted comparison, calculation, and condition values. Add a dedicated gold-standard import command that writes a versioned registry without modifying existing registries. The dynamic batch accepts a no-reparse mode for pre-parsed gold records; new articles continue to use the existing OpenAI parser and then enter the same dynamic verifier.

**Tech Stack:** Python 3.12, Pydantic v2, openpyxl, pytest, Streamlit.

---

### Task 1: Preserve all 12 slots in Registry import

**Files:**
- Modify: `core/claim_registry.py`
- Test: `tests/unit/test_claim_registry.py`

1. Add failing tests for `comparison`, `calculation`, and `condition` values from XLSX-style rows, plus accepted null slots.
2. Run the focused test and verify it fails because those fields are discarded.
3. Implement typed JSON/object conversion and pass all twelve slots into `ClaimSchema`.
4. Run `tests/unit/test_claim_registry.py` and confirm it passes.

### Task 2: Add a versioned gold XLSX importer

**Files:**
- Create: `tools/import_gold_standard_registry.py`
- Test: `tests/unit/test_gold_standard_registry_import.py`

1. Add a failing test that imports a fixture XLSX and verifies count, unique IDs, original Claim IDs, source dates, and all twelve slots.
2. Implement a command that imports sheet `01_Claim_12Slot_전체`, writes `claim_registry.jsonl` and `validation_report.json`, and records the gold schema/source version.
3. Run focused importer tests.

### Task 3: Expose explicit gold batch mode

**Files:**
- Modify: `tools/run_e2e_batch.py`
- Test: `tests/unit/test_run_e2e_batch.py`

1. Add a failing test proving the gold batch defaults to no reparse while a normal Registry still reparses HOLD claims.
2. Add `--preparsed-registry` that prevents reparse for all records and validates the Registry metadata.
3. Run focused batch tests.

### Task 4: Surface the canonical Registry in Streamlit operations

**Files:**
- Modify: `app/streamlit_app.py`
- Test: `tests/test_streamlit_app.py`

1. Add a failing UI smoke test for the canonical Registry status and selected path display.
2. Add a read-only operations panel that recognizes `gold_standard_v1` and links its validation artifact; it must not replace the new-article path.
3. Run UI smoke tests.

### Task 5: Build and verify the actual 1,542-row artifact

**Files:**
- Create: `data/claim_registry/gold_standard_v1/claim_registry.jsonl`
- Create: `data/claim_registry/gold_standard_v1/validation_report.json`
- Create: `artifacts/gold_standard_v1_dynamic_kosis_YYYYMMDD/`

1. Run the importer against the user-supplied XLSX.
2. Assert exactly 1,542 loadable records, unique source keys, preserved slot mapping, and allowed null counts.
3. Run the dynamic KOSIS E2E batch with `--preparsed-registry --live-kosis` and persist E2E results plus typed HOLD queues.
4. Run the focused suite and selected integration tests; commit only project code, tests, canonical Registry, and reports.
