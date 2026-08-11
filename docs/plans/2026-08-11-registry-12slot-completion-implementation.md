# Registry 12-Slot Completion Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Normalize comparison semantics and produce an auditable OpenAI-enriched 772-record registry batch with concept/profile/E2E artifacts.

**Architecture:** Add a pure Claim comparison normalizer before slot enrichment result validation. Use the existing bounded enrichment CLI with `CLAFACT_CLAIM_PROVIDER=openai`, then run deterministic concept mapping and profile-first E2E only from the derived artifacts.

**Tech Stack:** Python 3.12, Pydantic v2, OpenAI Responses API, KOSIS read-only adapter, pytest.

---

### Task 1: Normalize comparison-key aliases

**Files:**
- Create: `core/comparison_normalizer.py`
- Create: `tests/unit/test_comparison_normalizer.py`

1. Write a failing test for `{period: "전년 동월 대비"}` becoming `{basis: "전년 동월 대비"}`.
2. Run the focused test and observe failure.
3. Implement a pure normalizer that only rewrites known aliases and preserves direction.
4. Run focused tests.

### Task 2: Apply normalization to enrichment and calculation planning

**Files:**
- Modify: `core/claim_slot_enricher.py`
- Modify: `core/calculation_planner.py`
- Modify: `tests/unit/test_calculation_planner.py`

1. Add failing test for a `period`-key YoY Claim producing a two-cell GROWTH_RATE plan.
2. Run the test and observe failure.
3. Normalize before calculation validation and plan selection.
4. Run focused tests.

### Task 3: Add auditable 772-record OpenAI batch command

**Files:**
- Modify: `tools/enrich_claim_slots.py`
- Test: `tests/unit/test_claim_slot_enrichment_batch.py`

1. Add a failing test for explicit OpenAI provider metadata in the result summary.
2. Implement `--provider openai` and output guard that prevents overwriting the source directory.
3. Run the bounded command with `--limit 772 --execute` using process-only credentials.

### Task 4: Build deterministic concept sidecar and E2E run

**Files:**
- Create: `tools/run_registry_profile_batch.py`
- Test: `tests/unit/test_controlled_registry_pilot.py`

1. Build concept mappings from derived Claim rows using `concept_seed_v1.json`.
2. Write JSONL results, coverage report, and review queue in a distinct output directory.
3. Run against the registered profiles and read-only KOSIS adapter.

### Task 5: Verify and integrate

1. Run focused tests and full `python -m pytest -q`.
2. Record immutable run reports, never source Registry mutations.
3. Commit, merge to main, test again, and push.
