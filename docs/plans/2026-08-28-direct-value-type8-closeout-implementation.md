# Direct Value Type 8 Closeout Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Merge the already-completed 230-Claim ledger with the canonical 176 and latest 94 live results into one auditable final type-8 ledger.

**Architecture:** Preserve the latest 230-row ledger as the source of Claim classification truth. Overlay canonical live-result snapshots by child Claim ID, with the 94 rerun taking precedence over the 176 run, and derive final status only from strict official-evidence predicates.

**Tech Stack:** Python 3.11+, csv/json, pytest, existing Pydantic result contracts.

---

### Task 1: Define closeout merge behavior

**Files:**
- Create: `tests/unit/test_direct_value_type8_closeout.py`
- Create: `core/direct_value_type8_closeout.py`

1. Write failing tests for 230-row coverage, overlay precedence, and strict official completion.
2. Run the tests and confirm failure because the closeout module is absent.
3. Implement the minimal merge and summary functions.
4. Run the tests and confirm they pass.

### Task 2: Create the closeout compiler

**Files:**
- Create: `tests/unit/test_compile_direct_value_type8_closeout.py`
- Create: `tools/compile_direct_value_type8_closeout.py`

1. Write a failing artifact test for CSV, JSON, TXT, hashes, and exact coverage.
2. Run the test and confirm failure.
3. Implement loading of the 230 ledger, 176 live results, and 94 compact results.
4. Generate the final artifacts and rerun the test.

### Task 3: Compile real artifacts and verify

**Files:**
- Create: `deliverables/CLAFACT_AUTO_8번_직접값_최종마감_20260828/*`

1. Run the compiler against the real artifacts.
2. Verify 230 unique Claim IDs and zero coverage gaps.
3. Verify every official-complete row has coordinates, value, URL, hash, retrieval time, and verified publication.
4. Run focused and full regression tests.

### Task 4: Integrate and publish

1. Review staged files and exclude large raw responses and secrets.
2. Commit the closeout code and final artifacts.
3. Push the working branch.
4. Confirm the remote SHA and report whether main/dashboard deployment still requires merge.
