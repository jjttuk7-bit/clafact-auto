# Direct Value Claim 100 Reclassification Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reclassify all 100 direct-value Claim structure failures into direct-value recovery, another verification type, or official-verification exclusion, and persist the auditable result in the 230-row ledger.

**Architecture:** Freeze the 100 rows from the current ledger, rebuild their Claim inputs, and run one deterministic reclassification engine that reuses source grounding, numeric-role, observation, and direct-value type guards from the shared pipeline. Execute discovery, intermediate, and final-blind subsets in order, then merge the outcomes into the 230-row CSV.

**Tech Stack:** Python 3.12+, Pydantic v2, pytest, CSV/JSONL audit artifacts, existing unified Claim pipeline.

---

### Task 1: Freeze and validate the 100-row scope

**Files:**
- Create: `core/direct_value_claim_reclassification_scope.py`
- Create: `tools/build_direct_value_claim_reclassification_scope.py`
- Test: `tests/unit/test_direct_value_claim_reclassification_scope.py`

1. Write tests for exact reason selection, unique Claim IDs, 71/21/8 split preservation, and hidden final-blind source text.
2. Run the tests and confirm they fail because the scope module is missing.
3. Implement the minimal scope builder and CLI.
4. Run the tests and confirm they pass.

### Task 2: Implement deterministic reclassification

**Files:**
- Create: `core/direct_value_claim_reclassifier.py`
- Test: `tests/unit/test_direct_value_claim_reclassifier.py`

1. Write tests for direct-value retention, 6번 증감량, 7번 증감률, 비중, 기록, 순위, forecast exclusion, policy exclusion, and private-transaction exclusion.
2. Confirm the tests fail.
3. Implement the classifier by composing existing source-role and pipeline guard functions.
4. Confirm all tests pass, including ambiguity fail-closed cases.

### Task 3: Build the auditable runner and ledger merger

**Files:**
- Create: `tools/run_direct_value_claim_reclassification.py`
- Create: `tools/compile_direct_value_claim_reclassification_results.py`
- Test: `tests/unit/test_direct_value_claim_reclassification_results.py`

1. Write failing tests for 100-row coverage, mutually exclusive results, result evidence fields, and 230-row merge preservation.
2. Implement discovery/intermediate/final runner and merger.
3. Verify target count, split count, and result sum invariants.

### Task 4: Execute the frozen subsets

**Files:**
- Create: `artifacts/direct_value_claim_reclassification_v1/scope/manifest.json`
- Create: `artifacts/direct_value_claim_reclassification_v1/results/*.jsonl`

1. Build the frozen 100-row scope from the latest 230-row ledger.
2. Execute the 71 discovery rows and inspect aggregate rule failures.
3. Apply only generic fixes and execute the 21 intermediate rows.
4. Freeze the code and execute the 8 final-blind rows exactly once.

### Task 5: Compile outputs and verify

**Files:**
- Create: `deliverables/CLAFACT_AUTO_8번_직접값_230건_Claim구조100건재판정원장_20260828.csv`
- Create: `deliverables/CLAFACT_AUTO_8번_직접값_Claim구조100건재판정_결과보고_20260828.txt`

1. Merge all 100 outcomes into the 230-row ledger.
2. Verify 230 total rows, 100 executed rows, no duplicate Claim IDs, and three-way result total of 100.
3. Run focused tests and the full test suite.
4. Commit, push the feature branch, fast-forward `main`, and verify the remote SHA.
