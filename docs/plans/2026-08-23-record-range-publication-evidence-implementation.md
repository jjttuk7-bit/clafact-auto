# Record Range Publication Evidence Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Verify record-comparison history with one exact target-period official release plus per-row KOSIS last-change guards, while preserving explicit range-scoped audit evidence.

**Architecture:** Add explicit range-scope fields to publication/value provenance, implement a record-only batch fetch method in `OfficialValueFetcher`, and route only `RECORD_HIGH/LOW` plans through it. The method reuses the existing KOSIS range request, verifies the last requested period's official release, rejects any row changed after the article date, and never interprets `LST_CHN_DE` as a publication date.

**Tech Stack:** Python 3.12, Pydantic v2, dataclasses, pytest, KOSIS Parameter API, KOSIS statistics explanation API, official KOSTAT/MODS release pages.

---

### Task 1: Add explicit range-publication audit fields

**Files:**
- Modify: `core/kosis_publication.py`
- Modify: `core/kosis_fetcher.py`
- Modify: `schemas/verdict.py`
- Modify: `core/dynamic_kosis_verifier.py`
- Test: `tests/unit/test_record_range_publication_schema.py`

**Step 1: Write failing schema and provenance tests**

Create a `PublicationEvidence` representing a calculation range and a `KosisValue` with a parsed KOSIS last-change date. Convert it through `_value_provenance` and assert the verdict model preserves:

```python
publication.evidence_scope == "CALCULATION_RANGE"
publication.reference_period == "2025-06"
publication.coverage_start_period == "1999-06"
publication.coverage_end_period == "2025-06"
provenance.value_last_changed_at == date(2009, 3, 18)
```

Also assert the default remains `PERIOD` for existing direct-value evidence.

**Step 2: Run the test and verify RED**

Run: `python -m pytest tests/unit/test_record_range_publication_schema.py -q`

Expected: FAIL because the new audit fields do not exist.

**Step 3: Add minimal typed fields**

Add these optional/defaulted fields without weakening `extra="forbid"`:

```python
evidence_scope: Literal["PERIOD", "CALCULATION_RANGE"] = "PERIOD"
reference_period: str | None = None
coverage_start_period: str | None = None
coverage_end_period: str | None = None
```

to both `PublicationEvidence` and `OfficialPublicationProvenanceSchema`.

Add:

```python
value_last_changed_at: date | None = None
```

to `KosisValue` and `OfficialValueProvenanceSchema`. Map the fields in `_value_provenance`.

**Step 4: Run focused tests and verify GREEN**

Run: `python -m pytest tests/unit/test_record_range_publication_schema.py tests/unit/test_dynamic_kosis_verifier.py -q`

Expected: PASS.

**Step 5: Commit**

```bash
git add core/kosis_publication.py core/kosis_fetcher.py schemas/verdict.py core/dynamic_kosis_verifier.py tests/unit/test_record_range_publication_schema.py
git commit -m "feat: add range publication audit provenance"
```

### Task 2: Implement record-only range publication verification

**Files:**
- Modify: `core/kosis_fetcher.py`
- Test: `tests/unit/test_record_range_publication_fetcher.py`

**Step 1: Write the successful range test**

Build three monthly Evidence cells (`1999-06`, `2010-06`, `2025-06`), a batch API lookup returning all three official rows with `LST_CHN_DE`, and a publication lookup returning the exact `2025-06` release date.

Assert:

- `fetch_record_history` invokes the batch API once;
- publication lookup is called once for `2025-06`, never for historical periods;
- all three results are `SUCCESS`;
- all results carry `CALCULATION_RANGE` publication evidence;
- each result preserves its own `LST_CHN_DE` as `value_last_changed_at`;
- the publication date comes only from the official target-period release.

**Step 2: Run the successful test and verify RED**

Run: `python -m pytest tests/unit/test_record_range_publication_fetcher.py::test_record_history_uses_one_target_release_and_all_row_change_dates -q`

Expected: FAIL because `fetch_record_history` does not exist.

**Step 3: Implement the minimal successful path**

Add:

```python
def fetch_record_history(
    self,
    cells: list[EvidenceCellSchema],
    *,
    article_date: date,
) -> list[KosisValue]:
```

The method must:

1. require non-empty cells with one identical official coordinate;
2. call the existing API adapter's `fetch_many` once;
3. hash the complete response;
4. fetch publication evidence only for `cells[-1]`;
5. require exact verified publication evidence not after `article_date`;
6. match every requested Evidence cell to exactly one API row;
7. parse each `LST_CHN_DE` as an exact ISO date;
8. require each last-change date not after `article_date`;
9. return one successful `KosisValue` per cell with range-scoped publication evidence.

Create an actual range source URL covering the first and last requested periods. Do not label a single-period URL as the source of a range response.

**Step 4: Add fail-closed tests one at a time**

Add and verify RED/GREEN for:

- target release `UNRESOLVED` → all results `AS_OF_UNAVAILABLE`;
- target release `FETCH_FAILED` → `PUBLICATION_FETCH_FAILED`;
- release date after article date → `AS_OF_UNAVAILABLE`;
- missing, malformed, or post-article `LST_CHN_DE` → `AS_OF_UNAVAILABLE`;
- missing official value row → `NO_DATA` for the affected coordinate;
- mismatched coordinates or response count cannot produce success.

Run after each test: `python -m pytest tests/unit/test_record_range_publication_fetcher.py -q`

Expected: PASS after the minimal corresponding implementation.

**Step 5: Verify direct and non-record behavior is unchanged**

Run: `python -m pytest tests/unit/test_official_value_fetcher.py -q`

Expected: PASS.

**Step 6: Commit**

```bash
git add core/kosis_fetcher.py tests/unit/test_record_range_publication_fetcher.py
git commit -m "feat: verify record history with range publication evidence"
```

### Task 3: Route only record calculations through the new path

**Files:**
- Modify: `core/dynamic_kosis_verifier.py`
- Test: `tests/unit/test_record_range_publication_verifier.py`

**Step 1: Write failing routing tests**

Use a fake fetcher exposing `fetch`, `fetch_many`, and `fetch_record_history` call counters.

Assert:

- `RECORD_HIGH` and `RECORD_LOW` invoke `fetch_record_history` once;
- direct, difference, growth, share, and rank calculations do not invoke it;
- a record-range `AS_OF_UNAVAILABLE` produces an `OFFICIAL_VALUE_FETCH` HOLD with that exact reason;
- a successful record range reaches deterministic calculation and Verdict.

**Step 2: Run tests and verify RED**

Run: `python -m pytest tests/unit/test_record_range_publication_verifier.py -q`

Expected: FAIL because the verifier still calls generic `fetch_many`.

**Step 3: Add record-only dispatch**

In `verify_claim_against_kosis`, select `fetch_record_history` only when `calculation_type` is `RECORD_HIGH` or `RECORD_LOW` and the method is callable. Keep the existing `fetch_many` and per-cell fallbacks for all other calculation types and test fakes.

Do not catch a range publication failure and silently retry through a weaker generic path.

**Step 4: Run routing and verifier regression tests**

Run:

```bash
python -m pytest tests/unit/test_record_range_publication_verifier.py tests/unit/test_dynamic_kosis_verifier.py tests/unit/test_record_calculation_plan.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add core/dynamic_kosis_verifier.py tests/unit/test_record_range_publication_verifier.py
git commit -m "feat: route record calculations through range publication"
```

### Task 4: Expose range publication evidence in bounded CSV output

**Files:**
- Modify: `tools/run_record_comparison_group.py`
- Modify: `tests/unit/test_record_comparison_group_cli.py`

**Step 1: Write failing CSV tests**

Extend a schema-shaped record result and assert the CSV row contains:

```text
publication_evidence_scope=CALCULATION_RANGE
publication_reference_period=2025-06
publication_coverage=1999-06~2025-06
value_last_changed_dates=2009-03-18|...|2025-07-03
```

Direct-value rows must remain `PERIOD` or empty according to their actual provenance.

**Step 2: Run tests and verify RED**

Run: `python -m pytest tests/unit/test_record_comparison_group_cli.py -q`

Expected: FAIL because the CSV columns do not exist.

**Step 3: Add the audit columns**

Add the four columns to `CSV_FIELDS` and `_csv_row`. Read only actual typed provenance values; do not infer scope from Claim type or requested period count.

**Step 4: Run CSV tests and verify GREEN**

Run: `python -m pytest tests/unit/test_record_comparison_group_cli.py -q`

Expected: PASS.

**Step 5: Commit**

```bash
git add tools/run_record_comparison_group.py tests/unit/test_record_comparison_group_cli.py
git commit -m "feat: report range publication evidence in csv"
```

### Task 5: Execute the one-Claim official acceptance run

**Files:**
- Create: `artifacts/clafact_final_completion_202608/issue_group_harness/runs/record-comparison-008.csv`
- Create: `artifacts/clafact_final_completion_202608/issue_group_harness/runs/record-comparison-008.jsonl`

**Step 1: Confirm the official target release independently**

Use `KosisPublicationLookup` for `101:DT_1DA7002S`, period `2025-06`. Confirm the official release date is `2025-07-16`, the same as the frozen article date, and preserve only non-secret URLs/hashes.

**Step 2: Run only Claim `A02558_7`**

Use the existing bounded record-comparison runner with run id `record-comparison-008`, one explicit Claim ID, and a sufficient live budget. Do not run the full 1,542-Claim Registry.

**Step 3: Verify the actual result**

The record child must show:

- official table `101:DT_1DA7002S`;
- requested range `1999-06~2025-06` and count `27`;
- 27 official values and per-row last-change dates;
- target release date `2025-07-16` and official release URL/hash;
- `CALCULATION_RANGE` scope;
- deterministic record value/periods;
- final `RECORD_CONFIRMED` or `RECORD_NOT_CONFIRMED`, never a fabricated success.

If any official condition fails, preserve the exact HOLD and stop; do not relax the contract to force AUTO.

**Step 4: Commit actual evidence**

```bash
git add artifacts/clafact_final_completion_202608/issue_group_harness/runs/record-comparison-008.csv artifacts/clafact_final_completion_202608/issue_group_harness/runs/record-comparison-008.jsonl
git commit -m "test: verify record history with official range publication"
```

### Task 6: Complete regression verification and independent review

**Files:**
- Review all files changed since `6fe19ed`

**Step 1: Run the focused suite**

Run:

```bash
python -m pytest tests/unit/test_record_range_publication_schema.py tests/unit/test_record_range_publication_fetcher.py tests/unit/test_record_range_publication_verifier.py tests/unit/test_record_comparison_group_cli.py tests/unit/test_official_value_fetcher.py tests/unit/test_dynamic_kosis_verifier.py -q
```

Expected: PASS.

**Step 2: Run the complete suite**

Temporarily restore only the two ignored fixtures required by the existing tests, run `python -m pytest -q --disable-warnings`, and remove only those exact temporary copies afterward.

Expected: all tests PASS.

**Step 3: Request independent review**

Use @requesting-code-review. Require review of:

- no use of `LST_CHN_DE` as a publication date;
- no range evidence outside record calculations;
- exact target release and article-date comparison;
- all rows checked for missing/post-article last-change dates;
- actual range URL/hash and release URL/hash preserved;
- no Claim-ID-specific implementation;
- no downgrade from failed official lookup to guessed success.

Fix every Critical/Important finding, rerun focused and complete suites, and rerun the one-Claim official acceptance if behavior changed.

**Step 4: Commit review fixes if any**

```bash
git add <reviewed task files>
git commit -m "fix: enforce record range publication safeguards"
```

**Step 5: Push the branch**

Run: `git push origin codex/final-completion-execution`

Expected: the remote branch contains design, implementation, tests, and actual official-run evidence.
