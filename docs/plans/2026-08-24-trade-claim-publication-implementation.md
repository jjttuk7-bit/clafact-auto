# Trade Claim Official Publication Verification Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Restore trade Claim period/scope, split mixed total/subgroup/share numbers, and verify them against live Bank of Korea or Korea Customs Service publications.

**Architecture:** Add deterministic trade-scope recovery before admission, then extend the post-KOSIS publication verifier with exact-period official-board discovery and official PDF/HWP extraction. Keep KOSIS first, perform all calculations in Python, and preserve independent value/publication provenance.

**Tech Stack:** Python 3.12, Pydantic v2, urllib, pypdf, olefile, pytest

---

### Task 1: Trade period and scope recovery

**Files:**
- Create: `core/trade_claim_recovery.py`
- Modify: `core/validated_claim_recovery.py`
- Modify: `core/unified_claim_pipeline.py`
- Test: `tests/unit/test_trade_claim_recovery.py`

1. Write failing tests for `1~10일`, `1~20일`, annual cumulative end dates, deficit polarity, and the total/subgroup/share sentence.
2. Run `pytest tests/unit/test_trade_claim_recovery.py -q` and confirm the missing behavior fails.
3. Implement exact source-backed period recovery and deterministic split rules without Claim-ID conditions.
4. Re-run the focused tests and existing recovery tests.

### Task 2: Official publication discovery

**Files:**
- Create: `core/trade_publication_lookup.py`
- Test: `tests/unit/test_trade_publication_lookup.py`

1. Write failing tests using captured schema-shaped HTML for unique Bank of Korea and Customs board results, ambiguous results, wrong periods, and post-article publications.
2. Confirm the tests fail before implementation.
3. Implement trusted-host GET discovery with exact title/period validation.
4. Verify the focused tests pass.

### Task 3: Official PDF/HWP extraction and deterministic calculation

**Files:**
- Modify: `pyproject.toml`
- Modify: `requirements.txt`
- Create: `core/official_document_text.py`
- Modify: `core/official_publication_claim_verifier.py`
- Test: `tests/unit/test_trade_official_document_verifier.py`

1. Write failing tests for BOK monthly export level/growth, Customs cumulative trade balance, Customs country growth, and total/subgroup share calculation.
2. Confirm failures are caused by missing extractors.
3. Add `pypdf` and `olefile`; implement in-memory PDF/HWP text extraction and guarded value selection.
4. Build provenance with official page URL, attachment URL, publication date, retrieval time, and hashes.
5. Re-run focused and existing publication tests.

### Task 4: Canonical pipeline integration

**Files:**
- Modify: `core/official_engine_factory_v3.py`
- Modify: `core/official_evidence_service.py`
- Test: `tests/integration/test_trade_publication_pipeline.py`

1. Write a failing integration test proving KOSIS is attempted first and the exact official-author route runs only afterward.
2. Implement the minimal integration and stable trace reason codes.
3. Verify Streamlit, batch, and CLI all use the canonical factory unchanged.

### Task 5: Exact four-Claim live replay and ledger update

**Files:**
- Update: `artifacts/clafact_final_completion_202608/trade_claim_4_before_after_20260824.csv`
- Create: `artifacts/clafact_final_completion_202608/trade_claim_4_live_20260824/`
- Update four rows only in the protected ledger candidate.

1. Run only `A00489_11`, `A00673_9`, `A01180_3`, and `A01316_7` through the canonical live pipeline.
2. Export before/after results with all child Claim and provenance fields.
3. Verify exactly four parent rows changed in the ledger candidate and 1,538 stayed byte-equivalent by business columns.
4. Run focused tests, the full test suite, and live evidence checks.
5. Commit and push only reviewed code, tests, design, plan, and bounded audit artifacts.

