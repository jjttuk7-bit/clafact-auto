# Consumer Price Year-on-Year Verification Implementation Plan

> **For Codex:** REQUIRED SUB-SKILL: Use `executing-plans` to implement this plan task-by-task.

**Goal:** Verify a national monthly consumer-price year-on-year claim from an explicit KOSIS coordinate and an article-date-safe official snapshot.

**Architecture:** Map only the resolved `year_on_year_cpi_rate` semantic standard to KOSIS table `DT_1J22042`. The binding identifies the `T03` (year-on-year) item and the national `총지수` dimension; the Evidence Resolver turns that registered mapping into a confirmed coordinate. The Fetcher reads a versioned local snapshot recorded from the official 2025-10 release and applies the existing as-of guard.

**Tech Stack:** Python 3.12+, Pydantic v2, pytest, immutable JSON snapshots.

---

### Task 1: Add the semantic mapping regression test

**Files:**
- Modify: `tests/unit/test_evidence_resolver.py`

1. Create a `ClaimSchema` for `2025년 10월 소비자물가는 전년동월대비 2.4% 상승했다.`
2. Assert the explicit CPI binding resolves to table `DT_1J22042`, item `T03`, period `2025-10`, and confirmed national total coordinate.
3. Run the single test and confirm it fails before the mapping exists.

### Task 2: Register the explicit CPI binding and coordinate

**Files:**
- Modify: `data/semantic_standard/seed_concepts.json`
- Modify: `data/semantic_standard/kosis_bindings.json`
- Modify: `data/kosis_catalog/evidence_coordinates_goldset.json`

1. Add precise aliases for `소비자물가` and `소비자 물가`; do not add generic `물가`.
2. Register the monthly national `DT_1J22042` mapping.
3. Register `T03` and `총지수` as the official coordinate.
4. Implement only the resolver support necessary for the registered item to take precedence.
5. Re-run the regression test.

### Task 3: Add an immutable official snapshot

**Files:**
- Create: `data/kosis_snapshots/official_cpi_202510.json`
- Modify: `app/streamlit_app.py`
- Test: `tests/unit/test_kosis_fetcher.py`

1. Add a failing fetcher test for `DT_1J22042/T03`, `2025-10`, total index, and article date `2025-11-04`.
2. Record `2.4%` with KOSTAT’s 2025-10 official release metadata and release date; never use the article text as a source.
3. Add this snapshot to `SNAPSHOT_PATHS`.
4. Confirm the fetcher returns `SUCCESS` only when its `last_changed_at` is no later than the article date.

### Task 4: Run focused and full verification

1. Run focused resolver and fetcher tests.
2. Run `python -m pytest -q`, `python -m compileall -q app core schemas`, and `git diff --check`.
3. Commit and push the verified change.
