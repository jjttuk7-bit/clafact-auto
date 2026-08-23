# Explicit Previous-Month Recovery Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Resolve the safe explicit-previous-month subset of CONTEXT Claims, run it through the canonical official pipeline, and record the results in the consolidated 1,542-Claim ledger.

**Architecture:** Add one fail-closed time resolver that only accepts a unique bare month equal to the calendar month immediately preceding the article date. Re-admit only source-grounded Claims whose remaining contract passes, produce an auditable bounded Registry/CSV, run the existing canonical pipeline with stored slots, and rebuild the consolidated ledger.

**Tech Stack:** Python 3.12, Pydantic v2, pytest, KOSIS official API, CSV/JSONL artifacts.

---

## Scope and evidence

- Consolidated ledger CONTEXT remainder: 685 Claims.
- Missing `time` slot: 566 Claims.
- Missing only `time`: 461 Claims.
- Safe first pattern: source contains one bare `N월`, not a date (`N월 N일`) or range (`1~4월`), and `N월` equals the month immediately before `article_published_at`.
- The resolver must not infer arbitrary historical months or use a future month.
- A recovered Claim is admitted only when its numeric value is grounded in its target sentence and the executable Claim contract passes.

### Task 1: Fail-closed explicit-month resolver

**Files:**
- Modify: `core/claim_time_resolver.py`
- Test: `tests/unit/test_claim_time_resolver.py`

1. Write failing tests for a unique previous-month expression.
2. Write negative tests for a day expression, month range, non-previous month, and missing article date.
3. Run the focused tests and confirm RED.
4. Implement the minimal resolver.
5. Run the focused tests and confirm GREEN.

### Task 2: Safe re-admission

**Files:**
- Modify: `core/validated_claim_recovery.py`
- Test: `tests/unit/test_validated_claim_recovery.py`

1. Write a failing test showing a `MISSING_REQUIRED_SLOTS:time` Claim becomes `AUTO_OK` only after safe month recovery and source-value grounding.
2. Write negative tests for an ungrounded value and an unsafe month.
3. Run tests and confirm RED.
4. Integrate the resolver and executable-contract check.
5. Run tests and confirm GREEN.

### Task 3: Bounded group builder and audit CSV

**Files:**
- Create: `tools/build_explicit_previous_month_group.py`
- Create: `tests/unit/test_build_explicit_previous_month_group.py`

1. Write a failing CLI test with eligible and ineligible Registry records.
2. Require one output Registry row per admitted Claim and one audit row per evaluated candidate.
3. Record parent Claim ID, article date, source month, recovered time, before/after state, and reason.
4. Implement atomic JSONL/CSV output and a bounded `--limit`.
5. Run tests and confirm GREEN.

### Task 4: Actual official pipeline execution

**Files:**
- Create: `artifacts/clafact_final_completion_202608/explicit_previous_month_*/input_registry.jsonl`
- Create: `artifacts/clafact_final_completion_202608/explicit_previous_month_*/recovery_audit.csv`
- Create: `artifacts/clafact_final_completion_202608/explicit_previous_month_*/run/claim_verification_results.jsonl`
- Create: `artifacts/clafact_final_completion_202608/explicit_previous_month_*/run/coverage_report.json`

1. Build at most 20 safe Claims from the frozen Registry and consolidated ledger.
2. Run `tools/run_clafact_pipeline.py --stored-slots-only` so no LLM supplies official values.
3. Require actual Catalog/metadata/value/publication attempts from the canonical v3 engine.
4. Preserve exact failure stage and reason code where official evidence cannot be completed.

### Task 5: Ledger update and verification

**Files:**
- Modify: `artifacts/clafact_final_completion_202608/CLAFACT_1542_통합진행원장.csv`
- Modify: `artifacts/clafact_final_completion_202608/CLAFACT_1542_통합진행원장_요약.json`

1. Rebuild the consolidated ledger from all distributed results.
2. Verify exactly 1,542 unique parent rows and zero unmapped results.
3. Verify representative recovered and fail-closed Claims against their result JSONL.
4. Run focused tests and the repository regression suite.
5. Commit and push only the implementation, tests, plan, bounded artifacts, and updated ledger.
