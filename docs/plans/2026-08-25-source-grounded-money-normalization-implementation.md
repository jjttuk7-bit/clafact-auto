# Source-Grounded Money Normalization Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Normalize equivalent Structured Output currency scales to a source-grounded base-unit Claim before Admission and official verification.

**Architecture:** Add one deterministic normalization function to the existing trade Claim recovery boundary. It parses the Claim unit scale and the source currency expression independently, updates value/unit/polarity only when the normalized amounts agree, and leaves mismatches unchanged so the existing fail-closed grounding check can HOLD them.

**Tech Stack:** Python 3.12+, Pydantic v2, pytest, existing unified Claim pipeline

---

### Task 1: Freeze the Structured Output variant as a failing recovery test

**Files:**
- Modify: `tests/unit/test_trade_claim_recovery.py`

**Step 1: Write the failing test**

Add a Claim with `value=-1.056`, `unit="십억 달러"`, `time="연간 누계"`, and `frequency="YTD"`. Assert that recovery produces `value=-1_056_000_000`, `unit="달러"`, `time="2025-01-01/2025-02-20"`, `frequency="CUMULATIVE_PERIOD"`, and deficit polarity.

Add parameterized equivalents for `-10.56 억 달러` and `-1056000000 달러`. Add negative cases where the source amount differs or the currency is not dollars.

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_trade_claim_recovery.py -q`

Expected: the new positive scale-normalization test fails because value/unit remain `-1.056 십억 달러`.

### Task 2: Implement minimal source-grounded normalization

**Files:**
- Modify: `core/trade_claim_recovery.py`
- Test: `tests/unit/test_trade_claim_recovery.py`

**Step 1: Add the normalization boundary**

Add `normalize_trade_money(claim: ClaimSchema) -> ClaimSchema` and call it inside `recover_trade_period` before returning a recovered trade Claim. Parse only supported dollar units (`달러`, `천/만/억/십억/조 달러`) and source expressions ending in `달러`.

**Step 2: Enforce source equality**

Compute the absolute base-unit Claim amount and source amount. Update only when exactly one source monetary amount matches within deterministic floating-point tolerance. Preserve a negative Claim value; otherwise apply a negative sign for source `적자` and a positive sign for source `흑자`. Store `condition.polarity` consistently.

**Step 3: Run focused tests**

Run: `python -m pytest tests/unit/test_trade_claim_recovery.py tests/unit/test_validated_claim_recovery.py -q`

Expected: PASS.

### Task 3: Prove the canonical dashboard boundary uses the normalized Claim

**Files:**
- Modify: `tests/unit/test_unified_claim_pipeline.py`

**Step 1: Add the failing dashboard-boundary regression test**

Use a static extractor that returns the exact deployed Structured Output variant. Assert the official service receives base dollars, exact cumulative period, and `AUTO_OK` rather than stopping at Hard Guard.

**Step 2: Run the regression test**

Run: `python -m pytest tests/unit/test_unified_claim_pipeline.py -k trade_cumulative -q`

Expected: PASS after Task 2 and failure if normalization is removed.

**Step 3: Commit production code and tests**

Run:

```text
git add core/trade_claim_recovery.py tests/unit/test_trade_claim_recovery.py tests/unit/test_unified_claim_pipeline.py
git commit -m "fix: normalize source-grounded trade money"
```

### Task 4: Verify the supported pattern and deploy

**Files:**
- No additional source files expected.

**Step 1: Run the full suite**

Run: `python -m pytest -q`

Expected: all tests pass.

**Step 2: Run actual dashboard-path verification**

Run the canonical runtime with the article sentence `연간 누계 무역 수지는 10억5600만달러 적자다.` and article date `2025-02-21` using the configured OpenAI Structured Output and official APIs.

Expected: exact period, base-dollar Claim, official provenance, and `AUTO/MATCH`.

**Step 3: Push deployment branch**

Fast-forward `main` only after all checks pass, then verify that remote `main` points at the new commit. Confirm the Render deployment shows that commit before asking the user to retry.
