# Controlled Registry Pilot Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Run a read-only, 50-record OpenAI extraction and semantic-normalization pilot, then feed its derived artifacts into the reproducible multi-evidence E2E batch.

**Architecture:** `core/controlled_registry_pilot.py` converts selected immutable source records into derived registry records and a concept sidecar. It receives an injected structured extractor for tests and converts all failures to HOLD records. A CLI composes the existing settings/extractor/profile/E2E adapters and emits only caller-selected artifacts outside the source directory.

**Tech Stack:** Python 3.12, Pydantic v2, JSONL, existing OpenAI Responses adapter, pytest.

---

### Task 1: Create the typed controlled-pilot derivation service

**Files:**
- Create: `core/controlled_registry_pilot.py`
- Test: `tests/unit/test_controlled_registry_pilot.py`

**Step 1: Write the failing test**

```python
def test_pilot_limits_source_records_and_preserves_source_identity() -> None:
    result = derive_controlled_pilot(records, extractor, standard_path, limit=1)
    assert len(result.records) == 1
    assert result.records[0].article_id == "A1"
    assert result.records[0].sentence_id == "S1"
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_controlled_registry_pilot.py::test_pilot_limits_source_records_and_preserves_source_identity -q`

Expected: FAIL because `core.controlled_registry_pilot` does not exist.

**Step 3: Write minimal implementation**

Add `derive_controlled_pilot(records, extractor, standard_path, limit)` returning derived `ClaimRegistryRecord` objects, a `(article_id, sentence_id)` concept mapping, and reason counts. Reject a non-positive limit. Select records in input order.

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_controlled_registry_pilot.py::test_pilot_limits_source_records_and_preserves_source_identity -q`

Expected: PASS.

**Step 5: Commit**

```bash
git add core/controlled_registry_pilot.py tests/unit/test_controlled_registry_pilot.py
git commit -m "feat: derive controlled registry pilot claims"
```

### Task 2: Preserve failures as HOLD and map concepts deterministically

**Files:**
- Modify: `core/controlled_registry_pilot.py`
- Modify: `tests/unit/test_controlled_registry_pilot.py`

**Step 1: Write the failing tests**

```python
def test_pilot_converts_provider_failure_to_hold_without_dropping_record() -> None:
    result = derive_controlled_pilot(records, RaisingExtractor(), standard_path, limit=1)
    assert result.records[0].claim.parse_status == "HOLD"
    assert result.reason_counts["EXTRACTION_FAILED"] == 1

def test_pilot_creates_concept_sidecar_from_concept_seed() -> None:
    result = derive_controlled_pilot(records, BaechuExtractor(), standard_path, limit=1)
    assert result.concepts[("A1", "S1")].standard_key == "cpi_detail:A02A01701"
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/unit/test_controlled_registry_pilot.py -q`

Expected: FAIL because failure conversion and normalization are absent.

**Step 3: Write minimal implementation**

Catch extractor errors at the record boundary and construct a schema-valid HOLD Claim retaining source identity. Call `normalize_concept()` only when an extracted indicator is present. Do not map an unresolved concept to a profile.

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/unit/test_controlled_registry_pilot.py -q`

Expected: PASS.

### Task 3: Infer exact YoY growth plans and attach traces to early holds

**Files:**
- Modify: `core/calculation_planner.py`
- Modify: `core/e2e_batch_runner.py`
- Modify: `tests/unit/test_calculation_planner.py`
- Modify: `tests/unit/test_e2e_growth_batch.py`

**Step 1: Write the failing tests**

```python
def test_planner_infers_growth_rate_from_exact_yoy_basis_without_calculation_slot() -> None:
    assert build_calculation_plan(claim_with_yoy_basis_and_no_calculation, current).calculation_type == "GROWTH_RATE"

def test_e2e_batch_attaches_trace_when_concept_is_missing() -> None:
    assert result["execution_trace"]["events"][-1]["stage"] == "SEMANTIC_MATCH"
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/unit/test_calculation_planner.py tests/unit/test_e2e_growth_batch.py -q`

Expected: FAIL because the calculation slot is required and early holds bypass traces.

**Step 3: Write minimal implementation**

Treat only exact `comparison.basis == "전년 동월 대비"` as a GROWTH_RATE inference. Add a single E2E helper which appends a standardized trace before every return path.

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/unit/test_calculation_planner.py tests/unit/test_e2e_growth_batch.py -q`

Expected: PASS.

### Task 4: Add explicit pilot CLI and immutable artifact writers

**Files:**
- Create: `tools/run_controlled_registry_pilot.py`
- Modify: `tests/unit/test_controlled_registry_pilot.py`

**Step 1: Write the failing test**

```python
def test_write_pilot_artifacts_rejects_output_inside_source_directory(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="PILOT_OUTPUT_MUST_NOT_OVERLAP_SOURCE"):
        write_pilot_artifacts(result, source_path, source_path.parent)
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_controlled_registry_pilot.py::test_write_pilot_artifacts_rejects_output_inside_source_directory -q`

Expected: FAIL because artifact output guarding is absent.

**Step 3: Write minimal implementation**

Write `derived_registry.jsonl`, `concepts.json`, and `extraction_report.json` to a new output directory only. The CLI accepts source registry, output directory, `--limit` (default 50), standard path, profiles path, and optional snapshot files. It initializes the configured extractor through `Settings`, then invokes the existing E2E runner and writes `e2e_results.jsonl`, `coverage_report.json`, and a HOLD/review JSONL queue.

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_controlled_registry_pilot.py -q`

Expected: PASS.

**Step 5: Commit**

```bash
git add core/controlled_registry_pilot.py core/calculation_planner.py core/e2e_batch_runner.py tools/run_controlled_registry_pilot.py tests/unit/test_controlled_registry_pilot.py tests/unit/test_calculation_planner.py tests/unit/test_e2e_growth_batch.py
git commit -m "feat: run controlled registry verification pilot"
```

### Task 5: Verify and run the approved 50-record pilot

**Files:**
- Modify: `docs/plans/2026-08-11-controlled-registry-pilot-design.md`

**Step 1: Run focused tests**

Run: `python -m pytest tests/unit/test_controlled_registry_pilot.py tests/unit/test_calculation_planner.py tests/unit/test_e2e_growth_batch.py -q`

Expected: PASS.

**Step 2: Run full suite**

Run: `python -m pytest -q`

Expected: no failures.

**Step 3: Run the approved live pilot**

Run: `python tools/run_controlled_registry_pilot.py <source> <output> --limit 50`

Expected: an immutable derived registry, concept sidecar, E2E result JSONL, coverage report, and review queue. Report counts only; never output credentials.

**Step 4: Commit live-run metadata-safe documentation**

```bash
git add docs/plans/2026-08-11-controlled-registry-pilot-design.md docs/plans/2026-08-11-controlled-registry-pilot-implementation.md
git commit -m "docs: add controlled registry pilot runbook"
```
