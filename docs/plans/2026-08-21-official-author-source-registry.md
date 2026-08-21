# Official Author Source Registry Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a KOSIS-first, auditable official-author fallback that can verify a Claim only when an official release explicitly supplies the required value before the article date.

**Architecture:** The Core Engine keeps KOSIS Catalog, metadata, coordinate, value, and publication calls as the primary path. Only after KOSIS has actually attempted and cannot establish a valid coordinate/value does an `OfficialAuthorSourceRegistry` route the Claim to a configured source adapter. The first adapter targets Statistics Korea releases, preserves source URL, file hash, publication date, and extraction context, and returns no value unless period, indicator, unit, and release date all agree.

**Tech Stack:** Python 3.12, Pydantic v2, urllib, pypdf, pytest.

---

### Task 1: Define the common official-author evidence contract

**Files:**
- Create: `schemas/official_author.py`
- Modify: `schemas/verdict.py`
- Test: `tests/unit/test_official_author.py`

1. Write failing tests for a source result with `OFFICIAL_AUTHOR_RELEASE`, URL, publication date, document hash, and extraction snippet.
2. Run the test and confirm the contract does not exist.
3. Add strict Pydantic schemas; permit no untracked fields and no LLM-generated values.
4. Re-run tests.

### Task 2: Create the source registry and Statistics Korea adapter interface

**Files:**
- Create: `core/official_author_registry.py`
- Create: `core/kostat_release_value_fetcher.py`
- Test: `tests/unit/test_official_author_registry.py`

1. Write failing tests showing a Claim is routed by source authority, statistical domain, and indicator search terms rather than Claim ID or sentence text.
2. Run tests and confirm failure.
3. Implement registry lookup and a dependency-injected adapter protocol.
4. Re-run tests.

### Task 3: Retrieve and validate KOSTAT release documents

**Files:**
- Modify: `core/kosis_publication.py`
- Modify: `core/kostat_release_value_fetcher.py`
- Test: `tests/unit/test_kostat_release_value_fetcher.py`

1. Write failing tests for: finding the official release, following an official PDF attachment, rejecting releases after the article date, and preserving the SHA-256 digest.
2. Run tests and confirm failure.
3. Implement only direct `kostat.go.kr` access, PDF extraction through pypdf, and publication-date validation.
4. Re-run tests.

### Task 4: Extract an unambiguous official value

**Files:**
- Modify: `core/kostat_release_value_fetcher.py`
- Modify: `core/kosis_publication.py`
- Test: `tests/unit/test_kostat_release_value_fetcher.py`

1. Write failing tests that require period, indicator, compatible unit, and exactly one official value.
2. Run tests and confirm failure.
3. Implement deterministic extraction; reject multiple conflicting values, unsupported calculations, and missing source scope.
4. Re-run tests.

### Task 5: Integrate fallback after an actual KOSIS attempt

**Files:**
- Modify: `core/dynamic_kosis_verifier.py`
- Modify: `core/official_evidence_service.py`
- Modify: `core/official_engine_factory.py`
- Modify: `schemas/verdict.py`
- Test: `tests/unit/test_dynamic_kosis_verifier.py`
- Test: `tests/integration/test_official_author_fallback_e2e.py`

1. Write failing integration tests proving KOSIS remains first and a fallback is called only after a KOSIS coordinate/value attempt fails.
2. Run tests and confirm failure.
3. Add fallback dependency injection and use the existing deterministic calculator/verdict engine.
4. Preserve `OFFICIAL_AUTHOR_RELEASE` provenance and emit stable HOLD reasons when fallback fails.
5. Re-run tests.

### Task 6: Live acceptance and regression verification

**Files:**
- Create: `tools/run_official_author_acceptance.py`
- Test: `tests/integration/test_official_author_fallback_e2e.py`

1. Run the 2025 domestic rice-area Claim against real KOSIS and the KOSTAT release.
2. Verify KOSIS is attempted and the fallback obtains 677,597ha from the official document published 2025-08-28.
3. Verify Python calculates the verdict and saves both KOSIS diagnostics and official-author provenance.
4. Run the focused suite, then full `pytest` suite.
5. Commit only files owned by this feature after inspecting the diff.