# CPI Trace and Function Calling Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make registered CPI verification produce semantically complete claims, truthful execution traces, visible registered metadata, and a configurable constrained HCX Function Calling path.

**Architecture:** Add small deterministic adapters at existing boundaries. Claim post-processing derives only explicit comparison text; the CPI resolver exposes a registered concept and candidate; the trace recorder supports SKIPPED events; application wiring selects one of two HCX extractors without exposing verification functions to the model.

**Tech Stack:** Python 3.12+, Pydantic v2, pytest, Streamlit, HCX Structured Output/Function Calling.

---

### Task 1: Explicit comparison normalization

**Files:**
- Modify: `core/hcx_claim_extractor.py`
- Test: `tests/unit/test_hcx_prompt.py`

1. Write a failing test requiring `전년 동월 대비` to produce a non-null comparison map.
2. Run the focused test and confirm the expected assertion failure.
3. Add deterministic post-validation normalization shared by provider outputs.
4. Run the focused test and confirm PASS.

### Task 2: Registered CPI semantic metadata

**Files:**
- Modify: `core/cpi_growth_resolver.py`
- Test: `tests/unit/test_cpi_growth_resolver.py`

1. Write failing assertions for a registered standard concept and visible candidate.
2. Run the focused test and confirm RED.
3. Extend `CpiGrowthPlan` with the registered concept without changing official coordinates.
4. Run the focused test and confirm GREEN.

### Task 3: Truthful registered-route trace

**Files:**
- Modify: `schemas/pipeline_trace.py`
- Modify: `core/claim_verification_service.py`
- Modify: `app/streamlit_app.py`
- Test: `tests/unit/test_claim_verification_service.py`

1. Write a failing test requiring semantic mapping and catalog search to be SKIPPED for a registered profile.
2. Run the focused test and confirm RED.
3. Add immutable `skip_stage` support and a registered-profile trace method.
4. Wire the single and batch paths to the truthful trace sequence.
5. Run focused trace and CPI tests and confirm GREEN.

### Task 4: Configurable extractor selection

**Files:**
- Modify: `config/settings.py`
- Create: `core/claim_extractor_factory.py`
- Modify: `app/streamlit_app.py`
- Modify: `.env.example`
- Test: `tests/unit/test_claim_extractor_factory.py`

1. Write failing tests for default Structured Output, Function Calling selection, and invalid mode rejection.
2. Run them and confirm RED.
3. Implement the minimal factory and Streamlit wiring.
4. Run the focused tests and confirm GREEN.

### Task 5: Verification

**Files:**
- Test: `tests/unit/`
- Test: `tests/goldset/`

1. Run all focused regression tests.
2. Run the complete pytest suite.
3. Inspect `git diff` for authority-boundary violations and accidental secret changes.
4. Report files, execution instructions, test results, remaining TODOs, and the next recommended phase.

