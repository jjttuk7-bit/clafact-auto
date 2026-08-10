# Profile-First Path Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Deterministically select one registered verification profile from an exact semantic-standard key, safely falling back or holding when selection is unsafe.

**Architecture:** Add a pure `core.profile_first` selector with a small typed result object. It accepts the existing claim, normalized concept, and typed profiles; it never fetches data, computes values, bypasses Hard Guard, or creates a verdict. The caller uses `NOT_FOUND` to continue ordinary catalog search and must stop on `HOLD`.

**Tech Stack:** Python 3.12+, Pydantic v2, pytest.

---

### Task 1: Specify Profile-First selection behavior

**Files:**
- Create: `tests/unit/test_profile_first.py`

**Step 1: Write the failing test**

```python
def test_selects_the_profile_with_an_exact_standard_key() -> None:
    result = resolve_profile_first(claim, concept, [profile])
    assert result.status == "MATCHED"
    assert result.profile == profile
```

Add tests for no registered profile (`NOT_FOUND`), explicit calculation conflict (`HOLD`), duplicate matching keys (`HOLD`), and incomplete coordinates (`HOLD`).

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_profile_first.py -q`

Expected: FAIL because `core.profile_first` does not exist.

### Task 2: Implement the minimal pure selector

**Files:**
- Create: `core/profile_first.py`
- Test: `tests/unit/test_profile_first.py`

**Step 1: Implement the selector**

```python
def resolve_profile_first(claim, concept, profiles) -> ProfileFirstResolution:
    ...
```

Return only `MATCHED`, `NOT_FOUND`, or `HOLD`; use stable HOLD reason codes and only exact `standard_key` equality.

**Step 2: Run focused tests**

Run: `python -m pytest tests/unit/test_profile_first.py -q`

Expected: PASS.

### Task 3: Verify and commit

**Files:**
- Create: `core/profile_first.py`
- Create: `tests/unit/test_profile_first.py`

**Step 1: Run full suite**

Run: `python -m pytest -q`

Expected: all tests pass.

**Step 2: Commit**

```bash
git add core/profile_first.py tests/unit/test_profile_first.py docs/plans/2026-08-11-profile-first-path-implementation.md
git commit -m "feat: add profile-first selection path"
```
