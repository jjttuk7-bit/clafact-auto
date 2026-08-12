# Generalized Dynamic KOSIS Discovery Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make unseen 12-slot Claims enter contextual, bounded KOSIS discovery and return evidence-backed AUTO or a precise HOLD without sentence-specific code.

**Architecture:** Extend deterministic time normalization, replace the local-candidate short circuit with a structural-sufficiency decision, merge ranked official search results, cap metadata hydration, and preserve UI-safe stage diagnostics. Existing Hard Guard and deterministic verdict ordering remain unchanged.

**Tech Stack:** Python 3.12, Pydantic v2, pytest, Streamlit, KOSIS OpenAPI adapters

---

### Task 1: Relative period normalization

**Files:**
- Modify: `core/claim_time_resolver.py`
- Test: `tests/unit/test_claim_time_resolver.py`

1. Add failing tests for `올해 1분기`, `지난해 4분기`, and `올해 상반기` with an article date.
2. Run `python -m pytest tests/unit/test_claim_time_resolver.py -q` and confirm the new assertions fail.
3. Implement deterministic relative period resolution without LLM assistance.
4. Run the focused tests and confirm they pass.

### Task 2: Conditional contextual live discovery

**Files:**
- Modify: `core/catalog_discovery.py`
- Test: `tests/unit/test_catalog_discovery.py`

1. Add a failing test where generic local export candidates do not represent the Claim dimension `중고차` and live search must receive `중고차 수출액`.
2. Add a test where a structurally sufficient local candidate prevents an unnecessary live call.
3. Run the focused tests and confirm the expansion test fails for the existing local short circuit.
4. Implement a reusable local-candidate sufficiency predicate and merge/deduplicate ranked local and live identities.
5. Run the focused tests and confirm they pass.

### Task 3: Bounded metadata hydration

**Files:**
- Modify: `core/catalog_metadata_refresh.py`
- Modify: `app/streamlit_app.py`
- Test: `tests/unit/test_catalog_metadata_refresh.py`
- Test: `tests/test_streamlit_app.py`

1. Add a failing test that asserts only the configured top candidate budget is hydrated.
2. Set a conservative UI discovery budget and preserve remaining candidates as unresolved identities.
3. Run the focused tests and confirm they pass.

### Task 4: Stage-specific operational diagnostics

**Files:**
- Create: `core/operational_error.py`
- Modify: `app/streamlit_app.py`
- Test: `tests/unit/test_operational_error.py`
- Test: `tests/test_streamlit_app.py`

1. Add failing tests for stable stage codes, diagnostic IDs, and secret-free UI messages.
2. Wrap parser, catalog, metadata, and verification boundaries without converting semantic uncertainty into exceptions.
3. Log exception type and traceback server-side without request secrets or provider bodies.
4. Run focused tests and confirm they pass.

### Task 5: Regression and release verification

**Files:**
- Test: existing test suites

1. Execute the used-car export Claim through the same single-Claim engine and capture its resolved slots, search queries, route, reason code, and elapsed time.
2. Run `python -m pytest tests/unit -q`.
3. Run `python -m pytest tests/integration tests/goldset -q`.
4. Run `python -m pytest tests/test_streamlit_app.py -q`.
5. Run the 1,542-Claim offline/dynamic batch command using its existing artifact output directory and compare route/reason distributions without changing Registry inputs.
6. Review `git diff --check` and `git status --short`, stage only files created or modified for this plan, commit, and push `main`.
