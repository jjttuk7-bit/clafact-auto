# Official Author Fallback Five Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reprocess exactly five `KOSIS_CATALOG_UNAVAILABLE` child Claims through KOSIS-first and auditable official-author fallback paths.

**Architecture:** Wrap the canonical v3 official service with a fallback service that activates only after the KOSIS catalog operational hold. A profile registry selects one trusted official author by semantic fields, an HTTP adapter retrieves the official document, and deterministic extraction plus article-date guards produce the verdict and provenance.

**Tech Stack:** Python 3.12, Pydantic v2, urllib adapters, pytest, CSV/JSONL artifacts.

---

### Task 1: Freeze and classify the five inputs

**Files:**
- Create: `artifacts/clafact_final_completion_202608/official_author_fallback_5_20260824/input_registry.jsonl`
- Create: `artifacts/clafact_final_completion_202608/official_author_fallback_5_20260824/before.csv`
- Test: `tests/unit/test_official_author_fallback_input.py`

1. Write a failing test that selects only the five top-level `KOSIS_CATALOG_UNAVAILABLE` rows.
2. Run the focused test and confirm failure.
3. Implement deterministic selection and before-row export.
4. Run the focused test and confirm pass.

### Task 2: Add reusable official-author profiles and matching

**Files:**
- Create: `core/official_author_profiles.py`
- Create: `data/official_author/official_author_profiles_v1.json`
- Test: `tests/unit/test_official_author_profiles.py`

1. Write failing positive and ambiguous-profile tests.
2. Implement field-based matching using indicator, source hint, population, region and dimensions; never Claim IDs.
3. Run tests and confirm exact-one selection or fail-closed behavior.

### Task 3: Add official document fetch, extraction and guards

**Files:**
- Create: `core/official_author_fetcher.py`
- Create: `schemas/official_author.py`
- Modify: `schemas/verdict.py`
- Modify: `schemas/pipeline_trace.py`
- Test: `tests/unit/test_official_author_fetcher.py`

1. Write failing tests for trusted-domain enforcement, period/value/unit extraction, article-date rejection and provenance.
2. Implement HTTP retrieval with retries and secret-safe URLs.
3. Hash the raw response and parse only registered deterministic expressions.
4. Run focused tests.

### Task 4: Connect the fallback to the canonical pipeline

**Files:**
- Create: `core/official_author_fallback_service.py`
- Modify: `core/official_engine_factory_v3.py`
- Modify: `core/official_run_csv.py`
- Test: `tests/unit/test_official_author_fallback_service.py`
- Test: `tests/unit/test_official_run_csv.py`

1. Write a failing test proving KOSIS is called first and fallback runs only for `KOSIS_CATALOG_UNAVAILABLE`.
2. Implement the wrapper and trace stages.
3. Extend CSV output with official-author name, official document status, URL, retrieval time and hash.
4. Run focused tests.

### Task 5: Execute exactly five live Claims and merge results

**Files:**
- Create: `tools/run_official_author_fallback_group.py`
- Create: `artifacts/clafact_final_completion_202608/official_author_fallback_5_20260824/results.jsonl`
- Create: `artifacts/clafact_final_completion_202608/official_author_fallback_5_20260824/results.csv`
- Modify: `artifacts/clafact_final_completion_202608/multi_claim_official_15_live_20260824/final/claim_verification_results.jsonl`
- Modify: `artifacts/clafact_final_completion_202608/CLAFACT_1542_통합진행원장.csv`

1. Run the five-record command with real KOSIS credentials and official endpoints.
2. Verify five input IDs equal five output IDs and inspect every URL/hash/time.
3. Replace only these five child results in the 15-result set.
4. Rebuild the consolidated ledger and summary.

### Task 6: Regression, review, commit and push

1. Run focused official-author tests.
2. Run the full suite, deselecting only the two known external-registry artifact tests if still absent.
3. Review the diff for secrets, Claim-ID branching and accidental full-registry execution.
4. Commit and push `codex/final-completion-execution`.
