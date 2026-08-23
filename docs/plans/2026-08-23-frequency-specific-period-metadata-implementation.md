# Frequency-Specific KOSIS Period Metadata Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Preserve official KOSIS start/end periods by frequency and use only the Claim-matching range when planning historical record verification.

**Architecture:** Add a typed period-range value to `KosisCandidateSchema`, populate it while hydrating the already-fetched official PRD metadata, and make the deterministic calculation planner select the range matching the confirmed Evidence frequency. Keep legacy scalar period fields for compatibility, but never use a collapsed mixed-frequency scalar for record planning.

**Tech Stack:** Python 3.12, Pydantic v2, pytest, existing KOSIS official metadata/value adapters.

---

### Task 1: Add the typed period-range contract

**Files:**
- Modify: `schemas/candidate.py`
- Test: `tests/unit/test_candidate_period_ranges.py`

**Step 1: Write the failing schema round-trip test**

Create a candidate with monthly, quarterly, and annual ranges, call `model_dump()`, then reconstruct it with `model_validate()`. Assert that all exact start/end strings survive and that unknown fields remain forbidden.

```python
def test_candidate_period_ranges_survive_serialization_round_trip() -> None:
    candidate = KosisCandidateSchema(
        org_id="101", tbl_id="DT", tbl_name="고용률",
        period_ranges={
            "월": {"start_period": "1999.06", "end_period": "2026.07"},
            "분기": {"start_period": "1999 3/4", "end_period": "2026 2/4"},
            "년": {"start_period": "2000", "end_period": "2025"},
        },
        metadata_status="OFFICIAL_METADATA_READY",
    )
    restored = KosisCandidateSchema.model_validate(candidate.model_dump())
    assert restored.period_ranges["월"].start_period == "1999.06"
```

**Step 2: Run the test and verify RED**

Run: `python -m pytest tests/unit/test_candidate_period_ranges.py -q`

Expected: FAIL because `period_ranges` is not in the schema.

**Step 3: Add the minimal typed schema**

Add a `KosisPeriodRangeSchema` with optional `start_period` and `end_period`, `extra="forbid"`, then add:

```python
period_ranges: dict[str, KosisPeriodRangeSchema] = Field(default_factory=dict)
```

to `KosisCandidateSchema`.

**Step 4: Run the test and verify GREEN**

Run: `python -m pytest tests/unit/test_candidate_period_ranges.py -q`

Expected: PASS.

**Step 5: Commit**

```bash
git add schemas/candidate.py tests/unit/test_candidate_period_ranges.py
git commit -m "feat: add frequency-specific period ranges"
```

### Task 2: Preserve official PRD rows by frequency

**Files:**
- Modify: `core/catalog_metadata_refresh.py`
- Modify: `tests/unit/test_catalog_metadata_refresh.py`

**Step 1: Write failing mixed-frequency metadata tests**

Add a test whose official PRD response contains:

```python
[
    {"PRD_SE": "월", "STRT_PRD_DE": "1999.06", "END_PRD_DE": "2026.07"},
    {"PRD_SE": "분기", "STRT_PRD_DE": "1999 3/4", "END_PRD_DE": "2026 2/4"},
    {"PRD_SE": "년", "STRT_PRD_DE": "2000", "END_PRD_DE": "2025"},
]
```

Assert the three exact ranges are stored under their own normalized frequency. Add another test with duplicate monthly rows and assert minimum/month maximum are chosen only among monthly rows.

**Step 2: Run the tests and verify RED**

Run: `python -m pytest tests/unit/test_catalog_metadata_refresh.py -q`

Expected: FAIL because `period_ranges` is empty.

**Step 3: Implement grouping without another API request**

In `_with_period_metadata`, group each row using `_period_frequency`. Normalize non-empty start/end values and create one `KosisPeriodRangeSchema` per frequency. Update `period_ranges` with this mapping while keeping the existing legacy fields and `OFFICIAL_METADATA_READY` status.

The grouping must not compare a monthly string with a quarterly or annual string. Rows whose frequency cannot be identified do not enter `period_ranges`.

**Step 4: Run focused metadata tests**

Run: `python -m pytest tests/unit/test_catalog_metadata_refresh.py tests/unit/test_candidate_period_ranges.py -q`

Expected: PASS.

**Step 5: Commit**

```bash
git add core/catalog_metadata_refresh.py tests/unit/test_catalog_metadata_refresh.py
git commit -m "feat: preserve official periods by frequency"
```

### Task 3: Select only the matching official period range

**Files:**
- Modify: `core/calculation_planner_impl.py`
- Modify: `tests/unit/test_record_calculation_plan.py`
- Modify: `tests/unit/test_record_reference_period.py`

**Step 1: Write failing planner tests**

Add these cases:

1. A mixed-frequency candidate with `period_ranges` uses `1999.06` for a monthly same-month record plan.
2. A mixed-frequency candidate without `period_ranges` returns `None` instead of using a collapsed `start_period`.
3. A legacy single-frequency annual candidate still uses its scalar `start_period`.
4. A monthly Evidence cell cannot use an annual or quarterly range.

**Step 2: Run the tests and verify RED**

Run: `python -m pytest tests/unit/test_record_calculation_plan.py tests/unit/test_record_reference_period.py -q`

Expected: at least the mixed-frequency exact-selection test fails.

**Step 3: Add deterministic frequency selection**

Add a helper that normalizes the Evidence frequency (`월/M/month/monthly`, `분기/Q/quarter/quarterly`, `년/Y/year/annual`) and selects `candidate.period_ranges[normalized_frequency].start_period`.

Fallback to legacy `candidate.start_period` only when the candidate declares exactly one compatible frequency. Return `None` for missing, mixed, or incompatible metadata.

Use the selected start period for both ordinary record enumeration and same-month record enumeration.

**Step 4: Run focused record tests**

Run: `python -m pytest tests/unit/test_record_calculation_plan.py tests/unit/test_record_reference_period.py tests/unit/test_record_periods.py -q`

Expected: PASS.

**Step 5: Commit**

```bash
git add core/calculation_planner_impl.py tests/unit/test_record_calculation_plan.py tests/unit/test_record_reference_period.py
git commit -m "feat: plan records from matching official frequency"
```

### Task 4: Verify the real official metadata shape and selected Claim

**Files:**
- Modify: `artifacts/clafact_final_completion_202608/issue_group_harness/runs/record-comparison-006.csv`
- Modify: `artifacts/clafact_final_completion_202608/issue_group_harness/runs/record-comparison-006.jsonl`

**Step 1: Inspect the live official PRD response**

Use the existing repository/transport and configured environment key to fetch PRD metadata for official table `101:DT_1DA7002S`. Log only `PRD_SE`, `STRT_PRD_DE`, and `END_PRD_DE`; never log the API key.

Expected: the response exposes separate period rows or enough official fields to populate a monthly range. If it does not, stop this Claim at the period-metadata stage rather than infer a value.

**Step 2: Run only the bounded representative group**

Run the existing record-comparison group tool with Claim `A02558_7`, maximum one parent Claim, and run id `record-comparison-006`. Do not run the full 1,542-Claim Registry.

Expected: the direct-value child remains officially verified; the record child uses the exact monthly official start range and attempts the complete same-month history. A missing historical value or publication record must produce an explicit HOLD rather than a false record confirmation.

**Step 3: Validate the audit artifacts**

Assert CSV/JSONL contain:

- the selected official table and coordinates;
- first and final requested comparison periods;
- actual official request outcome;
- response content hashes for returned evidence;
- final verdict and exact stop reason.

**Step 4: Commit the bounded run evidence**

```bash
git add artifacts/clafact_final_completion_202608/issue_group_harness/runs/record-comparison-006.csv artifacts/clafact_final_completion_202608/issue_group_harness/runs/record-comparison-006.jsonl
git commit -m "test: rerun monthly record comparison with official periods"
```

### Task 5: Regression verification and review

**Files:**
- Review all files changed since `9bb52f0`

**Step 1: Run the focused suite**

Run:

```bash
python -m pytest tests/unit/test_candidate_period_ranges.py tests/unit/test_catalog_metadata_refresh.py tests/unit/test_record_calculation_plan.py tests/unit/test_record_reference_period.py tests/unit/test_record_periods.py -q
```

Expected: PASS.

**Step 2: Run the complete suite**

Temporarily restore only the two ignored Registry fixtures required by existing tests, run `python -m pytest -q --disable-warnings`, then remove only those temporary copies after resolving their exact worktree paths.

Expected: all tests PASS.

**Step 3: Review contract compliance**

Use @requesting-code-review to check:

- no Claim-ID-specific implementation;
- no cross-frequency period inference;
- no extra official request added;
- actual official metadata/value/publication attempts are traceable;
- incomplete history cannot produce a confirmed record verdict.

Fix every Critical or Important finding and rerun the affected tests plus the complete suite.

**Step 4: Commit any review fixes**

```bash
git add <reviewed task files>
git commit -m "fix: enforce official frequency period boundaries"
```

**Step 5: Push the branch**

Run: `git push origin codex/final-completion-execution`

Expected: remote branch advances with the design, implementation, tests, and bounded official-run evidence.
