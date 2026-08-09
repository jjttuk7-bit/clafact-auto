# Direction Sign Normalization Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Deterministically preserve the signed meaning of explicit Korean percentage increases and decreases after structured Claim extraction.

**Architecture:** Keep the LLM boundary unchanged. Add a small source-text-based normalizer in `core.claim_parser.py` after structured extraction and comparison backfill. It only transforms a non-negative percentage value when the source text explicitly contains a decrease marker; positive or already-negative values remain unchanged.

**Tech Stack:** Python 3.12, Pydantic v2, pytest.

---

### Task 1: Regression test for an explicit percentage decrease

**Files:**
- Modify: `tests/unit/test_claim_parser.py`
- Modify: `core/claim_parser.py`

**Step 1: Write the failing test**

```python
def test_parse_claim_normalizes_explicit_percentage_decrease_to_negative() -> None:
    result = parse_claim(
        "2025년 10월 배추 물가는 전년 동월 대비 34.5% 하락했다.",
        FakeStructuredExtractor(auto_claim(value=34.5, unit="%")),
    )
    assert result.value == -34.5
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_claim_parser.py::test_parse_claim_normalizes_explicit_percentage_decrease_to_negative -q`

**Step 3: Write minimal implementation**

Add a private helper that returns `-abs(value)` only for `%` claims whose source contains an explicit Korean decrease marker and a non-negative numeric value.

**Step 4: Run focused parser tests, then all tests**

Run: `python -m pytest tests/unit/test_claim_parser.py -q`
Run: `python -m pytest -q`

**Step 5: Commit and push**

```bash
git add core/claim_parser.py tests/unit/test_claim_parser.py docs/plans/2026-08-09-direction-sign-normalization-implementation.md
git commit -m "fix: normalize explicit decrease claim signs"
git push origin main
```
