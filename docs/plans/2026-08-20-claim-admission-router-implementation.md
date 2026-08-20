# Claim Admission Router Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a bounded Claim Admission Router that sends only eligible claims to the shared official KOSIS engine.

**Architecture:** A core router turns a candidate Claim into a six-label admission decision and auditable route result. An orchestration service invokes the existing limited-context reparser or deterministic splitter at most once, re-admits generated candidates, and invokes `OfficialEvidenceService` only for eligible claims.

**Tech Stack:** Python 3.12, Pydantic v2, pytest, existing OpenAI structured extractor and KOSIS official gateway adapters.

---

### Task 1: Define the admission data contract

**Files:**
- Create: `schemas/claim_admission.py`
- Create: `tests/unit/test_claim_admission.py`

**Steps:** Write failing tests for six labels, terminal statuses, reason codes, and audit events. Run `pytest tests/unit/test_claim_admission.py -v` and confirm an import failure. Add minimal typed Pydantic models for decisions, bounded retry state, events, and results. Rerun the test, then commit only these files.

### Task 2: Implement six-label rule router

**Files:**
- Create: `core/claim_admission_router.py`
- Create: `tests/unit/test_claim_admission_router.py`

**Steps:** Write failing real-Claim fixtures for complete KOSIS, missing context, multi-clause, private/company, forecast, and policy/definition examples. Run `pytest tests/unit/test_claim_admission_router.py -v` and confirm missing implementation. Implement ordered deterministic guards before eligibility; no official values may be generated or inspected. Rerun and commit only these files.

### Task 3: Orchestrate context, split, and safe terminal routes

**Files:**
- Create: `core/claim_admission_pipeline.py`
- Create: `tests/unit/test_claim_admission_pipeline.py`
- Modify: `core/claim_splitter.py`

**Steps:** Write failing tests proving one bounded context reparse, one split generation with child re-admission, no resolver invocation for excluded routes, and terminal `ADMISSION_ROUTED` output when retry limits are exhausted. Run `pytest tests/unit/test_claim_admission_pipeline.py -v`. Implement with injected extractor, contexts, splitter, router, and resolver. Preserve source IDs, produce deterministic child IDs and an event trace. Rerun and commit.

### Task 4: Connect the official batch entrypoint

**Files:**
- Create: `tools/run_claim_admission_e2e_batch.py`
- Create: `tests/integration/test_claim_admission_e2e_batch.py`

**Steps:** Write a failing integration test with an injected fake resolver proving that only eligible claims call it and that reports separate admission labels from official AUTO/HOLD results. Run the test, implement a resumable JSONL/report batch command, rerun, then commit. Official HOLD codes remain the exclusive output of an attempted official engine stage.

### Task 5: Verify and execute the population

**Files:**
- Create: `artifacts/claim_admission_e2e_20260820/`

**Steps:** Run focused unit and integration tests, then relevant existing parser/context/split/official E2E tests. Run the new command against all 1,542 candidates with configured KOSIS credentials, resuming safely if its live time budget expires. Independently validate population count, six-label distribution, event completeness, eligible-only resolver calls, AUTO/HOLD/MATCH/MISMATCH, and official HOLD reasons. Commit code/tests/docs separately from generated artifacts.
