# Canonical Pipeline Integration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Unify Streamlit, batch, and CLI on `unified_claim_pipeline` plus the v3 official engine, then run the full Registry against live official APIs and report success/failure counts.

**Architecture:** Add a canonical runtime/factory around the existing unified functions and expose a record-level verification function used by article and Registry paths. Keep Streamlit and batch as presentation adapters, and add resumable Registry execution plus deterministic reporting.

**Tech Stack:** Python, Pydantic v2, Streamlit, pytest, KOSIS OpenAPI, OpenAI Structured Outputs.

---

### Task 1: Record-level canonical contract

**Files:**
- Modify: `core/unified_claim_pipeline.py`
- Test: `tests/unit/test_unified_claim_pipeline.py`

1. Add failing tests proving article verification and Registry verification call the same recovery path and produce identical `PipelineEntry` contracts.
2. Run the focused tests and verify the expected missing-function failure.
3. Add `verify_registry_record` and make `verify_article` delegate to it.
4. Run the focused tests to green.

### Task 2: Canonical runtime factory

**Files:**
- Create: `core/canonical_pipeline.py`
- Test: `tests/unit/test_canonical_pipeline.py`

1. Add failing tests for one runtime object exposing article and record verification and for v3 factory construction.
2. Verify RED.
3. Implement the runtime and default path configuration with dependency injection for tests.
4. Verify GREEN.

### Task 3: Batch integration

**Files:**
- Modify: `core/batch_verifier.py`
- Test: `tests/unit/test_batch_verifier.py`

1. Add a failing test in which one article yields multiple `PipelineEntry` objects.
2. Verify RED.
3. Add canonical batch flattening while preserving the legacy verifier API.
4. Verify GREEN.

### Task 4: Streamlit integration

**Files:**
- Modify: `app/streamlit_app.py`
- Modify: `tests/test_streamlit_app.py`

1. Add source/integration tests requiring the canonical runtime and forbidding `BATCH_CLAIM_SPLIT_CARDINALITY`.
2. Verify RED.
3. Replace direct base-engine and per-sentence batch orchestration with canonical runtime calls.
4. Verify GREEN.

### Task 5: CLI and reporting integration

**Files:**
- Modify: `tools/run_clafact_pipeline.py`
- Create: `core/pipeline_run_reporting.py`
- Test: `tests/unit/test_clafact_pipeline_cli.py`
- Create: `tests/unit/test_pipeline_run_reporting.py`

1. Add failing tests proving the CLI uses record-level canonical verification and reports stage counts.
2. Verify RED.
3. Replace the separate batch recovery call, serialize canonical entries, and generate deterministic stage/failure reports.
4. Verify GREEN.

### Task 6: Resumable full Registry runner

**Files:**
- Modify: `tools/run_clafact_pipeline_bounded.py`
- Test: `tests/unit/test_bounded_pipeline_cli.py`

1. Add failing tests for checkpoint reuse and deterministic merge order.
2. Verify RED.
3. Persist per-parent results, add resume behavior, and preserve timeout/worker failures.
4. Verify GREEN.

### Task 7: Verification and live acceptance

**Files:**
- Output: `artifacts/clafact_full_registry_live_<date>/`

1. Run focused integration tests.
2. Run `python -m pytest -q` and require zero failures.
3. Execute the full 1542-record Registry with configured KOSIS and Structured Output credentials.
4. Resume until every parent has a terminal checkpoint.
5. Audit result counts and confirm report/result consistency.
6. Record actual AUTO, HOLD, operational failure, official resolution, and stage-level counts without converting failures into absence.

