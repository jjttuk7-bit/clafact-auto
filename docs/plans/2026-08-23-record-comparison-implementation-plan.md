# Official Record Comparison Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Split source-backed record assertions from direct-value assertions and verify `RECORD_HIGH`/`RECORD_LOW` against the complete comparable KOSIS history through the Claim period.

**Architecture:** Extend the existing Claim, calculation-plan, official-fetch, and Verdict contracts rather than adding a parallel verifier. A deterministic record splitter creates two child Claims when the source contains both a numeric level and a record assertion; the record child re-enters the same official engine and expands its confirmed current Evidence coordinate across the official metadata start period through the Claim period.

**Tech Stack:** Python 3.12-compatible code, Pydantic v2 schemas, pytest, existing KOSIS official adapters, CSV/JSONL issue-group artifacts.

---

### Task 1: Define record Claim splitting and admission contracts

**Files:**
- Create: `core/record_comparison_splitter.py`
- Modify: `core/admission_recovery.py`
- Modify: `core/admission_recovery_v3.py`
- Modify: `core/recovery_stage_audit.py`
- Modify: `core/validated_claim_recovery.py`
- Modify: `core/claim_contract_impl.py`
- Test: `tests/unit/test_record_comparison_splitter.py`
- Test: `tests/unit/test_record_comparison_admission.py`

**Step 1: Write failing tests**

- A source-backed `1419억달러 + 역대 최대` Claim produces two stable child IDs.
- The direct child has `calculation="DIRECT_VALUE"` and no record comparison.
- The record child has `calculation="RECORD_HIGH"` and retains `comparison.type="RECORD_HIGH"`.
- Both children retain the immutable parent sentence and lineage.
- A record assertion missing value, unit, or time remains pre-verification with a precise missing-slot reason.

**Step 2: Run tests and confirm RED**

Run: `python -m pytest -q tests/unit/test_record_comparison_splitter.py tests/unit/test_record_comparison_admission.py`

Expected: failures because record splitting and supported calculations do not exist.

**Step 3: Implement the minimal contract**

- Add `RECORD_HIGH` and `RECORD_LOW` to supported Claim calculations.
- Permit only matching record comparison types.
- Generate deterministic children without Claim-ID or sentence-specific branches.
- Route both complete children through `OfficialEvidenceResolver.resolve`.
- Mark `CLAIM_SPLIT` PASS for `RECORD_COMPARISON_SPLIT`.

**Step 4: Run tests and confirm GREEN**

Run the Task 1 command and require zero failures.

**Step 5: Commit**

Commit message: `feat: split record comparison claims`

### Task 2: Build complete historical Evidence plans

**Files:**
- Modify: `schemas/evidence.py`
- Modify: `core/calculation_planner_impl.py`
- Create: `core/record_periods.py`
- Test: `tests/unit/test_record_periods.py`
- Test: `tests/unit/test_calculation_planner.py`

**Step 1: Write failing tests**

- Annual periods expand from `1995` through `2024`.
- Monthly formats `1975.01`, `2024-12`, and `202412` normalize and preserve the current cell's format.
- Quarterly periods expand through the exact Claim quarter.
- A start period after the Claim period, missing start metadata, unsupported frequency, or excessive range returns no plan.
- Every generated cell preserves table, item, dimensions, unit, and changes only period and canonical key.

**Step 2: Run tests and confirm RED**

Run: `python -m pytest -q tests/unit/test_record_periods.py tests/unit/test_calculation_planner.py`

**Step 3: Implement the minimal planner**

- Add `RECORD_HIGH` and `RECORD_LOW` to `CalculationPlan.calculation_type`.
- Enumerate only `년/Y/YEAR`, `월/M/MONTH`, and `분기/Q/QUARTER` periods.
- Use `candidate.start_period` and the confirmed current cell period.
- Cap the range with a stable safety limit and return `None` rather than truncating.

**Step 4: Run tests and confirm GREEN**

Run the Task 2 command and require zero failures.

**Step 5: Commit**

Commit message: `feat: plan official record history`

### Task 3: Calculate and audit record verdicts

**Files:**
- Modify: `core/calculator_impl.py`
- Modify: `schemas/verdict.py`
- Modify: `core/dynamic_kosis_verifier.py`
- Test: `tests/unit/test_calculator.py`
- Test: `tests/unit/test_dynamic_kosis_record_comparison.py`

**Step 1: Write failing tests**

- `RECORD_HIGH` returns the maximum and `RECORD_LOW` returns the minimum.
- Empty history fails deterministically.
- A tied maximum matches.
- A current value below the historical maximum mismatches.
- Any missing, failed, unpublished-as-of, or count-mismatched official value produces stage-specific HOLD.
- The Verdict retains comparison type, start/end period, observed count, record value, and all record periods.

**Step 2: Run tests and confirm RED**

Run: `python -m pytest -q tests/unit/test_calculator.py tests/unit/test_dynamic_kosis_record_comparison.py`

**Step 3: Implement the minimal execution**

- Calculate extrema in Python only.
- Use the existing `fetch_many` official range request and existing publication/as-of checks.
- Compare the source-backed Claim value to the official extrema with existing unit conversion and tolerance.
- Attach a typed record-comparison summary and all Evidence/value provenance to the Verdict.

**Step 4: Run tests and confirm GREEN**

Run the Task 3 command and require zero failures.

**Step 5: Commit**

Commit message: `feat: verify official historical records`

### Task 4: Prove the shared Article, Registry, and official-engine flow

**Files:**
- Test: `tests/integration/test_record_comparison_unified_pipeline.py`
- Modify only if the failing test proves a missing connection: `core/unified_claim_pipeline.py`, `core/admission_recovery_v3.py`, or `core/official_evidence_service.py`

**Step 1: Write a failing integration test**

Build one structured record Claim, use official-adapter fakes at the network boundary, and assert:

- two child Claims and immutable lineage;
- both children call the same official service;
- the record child requests the complete historical coordinate range;
- Catalog, metadata, Hard Guard, matching, Evidence, value fetch, calculation, and Verdict trace stages are present;
- the record child returns MATCH only from official values.

**Step 2: Run and confirm RED**

Run: `python -m pytest -q tests/integration/test_record_comparison_unified_pipeline.py`

**Step 3: Connect only the missing shared-path behavior**

Do not add a special UI, batch, or Claim-ID branch.

**Step 4: Run and confirm GREEN**

Run the Task 4 command and the related admission/official-engine regression tests.

**Step 5: Commit**

Commit message: `test: cover unified record comparison flow`

### Task 5: Run a bounded real-KOSIS pattern group and persist evidence

**Files:**
- Create: `tools/run_record_comparison_group.py`
- Create: `tests/unit/test_record_comparison_group_cli.py`
- Create at runtime: `artifacts/clafact_final_completion_202608/issue_group_harness/runs/record-comparison-001.csv`
- Create at runtime: `artifacts/clafact_final_completion_202608/issue_group_harness/runs/record-comparison-001.jsonl`

**Step 1: Write a failing CLI contract test**

Require explicit Registry path, explicit Claim IDs or a bounded `--limit`, run ID, and output directory. Reject unbounded execution. Record before/after status, child type, official table, period range, observed count, record value/period, source URL, hashes, and trace.

**Step 2: Run and confirm RED**

Run: `python -m pytest -q tests/unit/test_record_comparison_group_cli.py`

**Step 3: Implement and verify the bounded runner**

- Reuse `unified_claim_pipeline` and v3 official engine.
- Do not run all 1,542 Claims.
- Execute only the selected record pattern Claims.
- Never mark official evidence true without actual KOSIS value and publication calls.

**Step 4: Run the real pattern group**

Execute the smallest available source-backed record Claim set with configured KOSIS credentials. If an official stage fails, retain its exact reason and request trace; do not replace it with a synthetic success.

**Step 5: Verify, review, commit, and push**

Run focused tests, then `python -m pytest -q --disable-warnings` with required local artifacts available. Run `git diff --check`. Request code review and fix every Critical/Important issue. Commit message: `feat: execute bounded record comparison group`.
