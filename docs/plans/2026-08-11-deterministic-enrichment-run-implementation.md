# Deterministic Enrichment Run Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Apply explicit slot rules to a complete Claim Registry without an LLM and emit an auditable local enrichment result and coverage report.

**Architecture:** Add a deterministic batch function that copies every source record, enriches only `AUTO_OK` Claims, and marks ambiguous directional claims `HOLD`. Keep the source Registry immutable; a CLI writes a separate JSONL result and JSON report whose metrics are derived from the emitted records.

**Tech Stack:** Python 3.12+, Pydantic v2, stdlib JSON, pytest.

---

### Task 1: Specify deterministic batch outcomes

**Files:**
- Create: `core/deterministic_slot_enrichment_batch.py`
- Create: `tests/unit/test_deterministic_slot_enrichment_batch.py`

**Step 1: Write failing tests**

Cover direct-value enrichment, explicit year-over-year enrichment, ambiguous-direction HOLD, and unchanged non-`AUTO_OK` records.

**Step 2: Verify the focused test fails**

Run: `python -m pytest tests/unit/test_deterministic_slot_enrichment_batch.py -q`
Expected: FAIL because the module does not exist.

**Step 3: Implement the minimal batch function**

Copy source records, apply `infer_explicit_slots`, retain source fields, and attach per-record audit status.

**Step 4: Verify the focused test passes**

Run: `python -m pytest tests/unit/test_deterministic_slot_enrichment_batch.py -q`
Expected: PASS.

### Task 2: Produce a reproducible coverage report

**Files:**
- Modify: `core/deterministic_slot_enrichment_batch.py`
- Modify: `tests/unit/test_deterministic_slot_enrichment_batch.py`

**Step 1: Write failing report tests**

Verify counts for source/processed/skipped/held/catalog-ready records, parse statuses, and non-empty comparison/calculation/condition slots.

**Step 2: Run focused tests**

Run: `python -m pytest tests/unit/test_deterministic_slot_enrichment_batch.py -q`
Expected: FAIL before report implementation.

**Step 3: Implement report generation**

Derive every metric from the emitted records, without claiming 1,532 records.

**Step 4: Verify focused tests pass**

Run: `python -m pytest tests/unit/test_deterministic_slot_enrichment_batch.py -q`
Expected: PASS.

### Task 3: Add a local-output CLI and verify

**Files:**
- Create: `tools/run_deterministic_slot_enrichment.py`
- Create: `tests/unit/test_run_deterministic_slot_enrichment.py`

**Step 1: Write failing CLI tests**

Verify a JSONL input writes `deterministic_enriched_claims.jsonl` and `coverage_report.json` only beneath the requested output directory.

**Step 2: Run focused tests**

Run: `python -m pytest tests/unit/test_run_deterministic_slot_enrichment.py -q`
Expected: FAIL before the CLI exists.

**Step 3: Implement the CLI**

Require explicit input and output paths, load JSONL, call the batch function, and write UTF-8 JSONL/JSON output.

**Step 4: Verify and commit**

Run: `python -m pytest tests/unit/test_deterministic_slot_enrichment_batch.py tests/unit/test_run_deterministic_slot_enrichment.py -q`

Run: `python -m pytest -q`

```powershell
git add core/deterministic_slot_enrichment_batch.py tools/run_deterministic_slot_enrichment.py tests/unit/test_deterministic_slot_enrichment_batch.py tests/unit/test_run_deterministic_slot_enrichment.py docs/plans/2026-08-11-deterministic-enrichment-run-implementation.md
git commit -m "feat: add deterministic registry enrichment run"
```
