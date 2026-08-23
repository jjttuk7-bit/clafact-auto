# Issue-Group Execution Harness Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Classify every baseline Claim into one primary problem group, run only a bounded slice through that group's allowed pipeline stages, record before/after results in Korean CSV ledgers, and prevent a full Registry rerun until every required group gate is valid.

**Architecture:** Add a deterministic control layer around the existing canonical pipeline and `RegistryStageRunner`; do not duplicate official lookup, calculation, or verdict logic. The harness reads frozen Registry/baseline JSONL, produces a master work ledger, selects 1–50 Claims from one group, delegates only the permitted stage range to an injected group executor, records a run ledger, and evaluates version-bound completion gates. A separate guard is the only path that can authorize a final full run.

**Tech Stack:** Python 3.12, Pydantic v2 project schemas, standard-library CSV/JSON, pytest, existing canonical pipeline and v3 official evidence service.

---

### Task 1: Deterministic primary issue classification

**Files:**
- Create: `core/issue_group_harness.py`
- Test: `tests/unit/test_issue_group_harness.py`

**Step 1: Write the failing tests**

Add parameterized tests covering every known terminal reason, `AUTO`, unknown reasons, and a row with multiple observed failures. Assert that exactly one `primary_group` is chosen from the earliest failing pipeline stage and that later failures are retained as `secondary_issues`.

**Step 2: Run tests to verify RED**

Run: `python -m pytest tests/unit/test_issue_group_harness.py -v`

Expected: FAIL because `core.issue_group_harness` does not exist.

**Step 3: Implement the minimal classifier**

Create `IssueGroup` and `ClaimIssueRecord`, the reason-to-group table, pipeline stage ordering, `terminal_reason(row)`, `observed_failures(row)`, and `classify_claim(row)`. Map unknown reasons to `UNCLASSIFIED`; never guess.

**Step 4: Run tests to verify GREEN**

Run: `python -m pytest tests/unit/test_issue_group_harness.py -v`

Expected: PASS.

**Step 5: Commit**

```bash
git add core/issue_group_harness.py tests/unit/test_issue_group_harness.py
git commit -m "feat: classify claims into primary issue groups"
```

### Task 2: Master and group CSV ledgers

**Files:**
- Modify: `core/issue_group_harness.py`
- Test: `tests/unit/test_issue_group_harness.py`

**Step 1: Write the failing tests**

Test `build_issue_registry()` against duplicate and missing Claim identifiers. Test `write_issue_ledgers()` for UTF-8 BOM, Korean headers, one master row per Claim, one group file per primary group, and group totals reconciling exactly to the master row count.

**Step 2: Run tests to verify RED**

Run: `python -m pytest tests/unit/test_issue_group_harness.py -v`

Expected: FAIL because the ledger functions are missing.

**Step 3: Implement the minimal ledger writer**

Use stable Korean headers and atomic temporary-file replacement. Include Claim/article identifiers, source sentence, domain, 12-slot audit summary, current stop stage/reason, primary/secondary issues, next allowed stage, before/after status and reason, table/source information, attempt count, code/data version, and timestamps. Write `claim_issue_master.csv`, `groups/*.csv`, and `group_summary.csv`.

**Step 4: Run tests to verify GREEN**

Run: `python -m pytest tests/unit/test_issue_group_harness.py -v`

Expected: PASS.

**Step 5: Commit**

```bash
git add core/issue_group_harness.py tests/unit/test_issue_group_harness.py
git commit -m "feat: write issue-group work ledgers"
```

### Task 3: Bounded group selection and stage ceilings

**Files:**
- Modify: `core/issue_group_harness.py`
- Test: `tests/unit/test_issue_group_harness.py`

**Step 1: Write the failing tests**

Test that selection requires one explicit group, rejects `UNCLASSIFIED`, rejects limits outside 1–50, and returns a stable slice. Inject stage handlers and assert that stages beyond the selected group's ceiling are never called.

**Step 2: Run tests to verify RED**

Run: `python -m pytest tests/unit/test_issue_group_harness.py -v`

Expected: FAIL because group selection/execution is missing.

**Step 3: Implement the minimal bounded harness**

Add `GroupPolicy`, the fixed allowed start/end stage table, `select_group_slice()`, and `run_group_slice()`. Require an injected executor implementing the selected policy; reject an executor result containing a downstream stage not allowed by the policy.

**Step 4: Run tests to verify GREEN**

Run: `python -m pytest tests/unit/test_issue_group_harness.py -v`

Expected: PASS.

**Step 5: Commit**

```bash
git add core/issue_group_harness.py tests/unit/test_issue_group_harness.py
git commit -m "feat: enforce bounded issue-group execution"
```

### Task 4: Before/after run ledger and gate evaluation

**Files:**
- Modify: `core/issue_group_harness.py`
- Test: `tests/unit/test_issue_group_harness.py`

**Step 1: Write the failing tests**

Test one executed slice containing improvement, unchanged failure, and a failure that moves backward. Assert creation of `runs/<run_id>.csv`, master ledger updates by Claim identifier, correct improvement counts, and gate rejection when any result lacks before/after evidence or regresses to an earlier stage.

**Step 2: Run tests to verify RED**

Run: `python -m pytest tests/unit/test_issue_group_harness.py -v`

Expected: FAIL because comparison and gates are missing.

**Step 3: Implement comparison and gates**

Add `compare_result()`, `record_group_run()`, `GroupGateResult`, and `evaluate_group_gate()`. For official stages, require trace/provenance evidence before accepting improvement. Persist gate state with code and data fingerprints.

**Step 4: Run tests to verify GREEN**

Run: `python -m pytest tests/unit/test_issue_group_harness.py -v`

Expected: PASS.

**Step 5: Commit**

```bash
git add core/issue_group_harness.py tests/unit/test_issue_group_harness.py
git commit -m "feat: record group improvements and completion gates"
```

### Task 5: Final full-run interlock

**Files:**
- Modify: `core/issue_group_harness.py`
- Test: `tests/unit/test_issue_group_harness.py`

**Step 1: Write the failing tests**

Test rejection when a required group gate is missing, failed, or bound to stale code/data fingerprints. Test success only when all required gates pass and explicit final authorization is true.

**Step 2: Run tests to verify RED**

Run: `python -m pytest tests/unit/test_issue_group_harness.py -v`

Expected: FAIL because the final-run guard is missing.

**Step 3: Implement the guard**

Add `authorize_final_full_run()`. Keep `REGRESSION` and `UNCLASSIFIED` out of required improvement gates, but require zero `UNCLASSIFIED` rows before authorization. Return a structured denial with every unmet condition.

**Step 4: Run tests to verify GREEN**

Run: `python -m pytest tests/unit/test_issue_group_harness.py -v`

Expected: PASS.

**Step 5: Commit**

```bash
git add core/issue_group_harness.py tests/unit/test_issue_group_harness.py
git commit -m "feat: lock final full run behind group gates"
```

### Task 6: Harness CLI and canonical executor adapter

**Files:**
- Create: `tools/run_issue_group_harness.py`
- Create: `core/issue_group_executor.py`
- Test: `tests/unit/test_issue_group_harness_cli.py`
- Test: `tests/integration/test_issue_group_executor.py`

**Step 1: Write the failing tests**

Test CLI subcommands `classify`, `run-group`, `gate`, and `authorize-final`. Verify `run-group` requires `--group` and defaults to 20 with a maximum of 50. In integration tests, inject the canonical components and assert the requested group adapter returns only allowed trace stages and delegates official lookup to the existing service.

**Step 2: Run tests to verify RED**

Run: `python -m pytest tests/unit/test_issue_group_harness_cli.py tests/integration/test_issue_group_executor.py -v`

Expected: FAIL because the CLI and adapter do not exist.

**Step 3: Implement the CLI and adapters**

`classify` reads frozen baseline JSONL and writes ledgers without network calls. `run-group` reads the master/group ledger, selects 1–50 rows, builds only the group's canonical stage adapter, and records results. `authorize-final` only reports authorization; it does not implicitly execute the full Registry.

**Step 4: Run tests to verify GREEN**

Run: `python -m pytest tests/unit/test_issue_group_harness_cli.py tests/integration/test_issue_group_executor.py -v`

Expected: PASS.

**Step 5: Commit**

```bash
git add core/issue_group_executor.py tools/run_issue_group_harness.py tests/unit/test_issue_group_harness_cli.py tests/integration/test_issue_group_executor.py
git commit -m "feat: add issue-group harness CLI"
```

### Task 7: Apply classification to the frozen 1,542-Claim baseline

**Files:**
- Generate: `artifacts/clafact_final_completion_202608/issue_group_harness/claim_issue_master.csv`
- Generate: `artifacts/clafact_final_completion_202608/issue_group_harness/group_summary.csv`
- Generate: `artifacts/clafact_final_completion_202608/issue_group_harness/groups/*.csv`

**Step 1: Run classification without network calls**

Run:

```bash
python tools/run_issue_group_harness.py classify artifacts/clafact_final_completion_202608/full_registry_latest_live_20260823/claim_verification_results.jsonl artifacts/clafact_final_completion_202608/issue_group_harness
```

Expected: exactly 1,542 master rows, no duplicate Claim identity, and group totals equal 1,542.

**Step 2: Inspect representative rows**

Check at least one row from every group, all `UNCLASSIFIED` rows, and the 13 regression rows. Correct classification rules in code through a new failing test before changing behavior.

**Step 3: Commit generated ledgers**

```bash
git add artifacts/clafact_final_completion_202608/issue_group_harness
git commit -m "data: classify baseline claims into issue groups"
```

### Task 8: Verification and first bounded execution

**Files:**
- Generate: `artifacts/clafact_final_completion_202608/issue_group_harness/runs/<run_id>.csv`
- Modify: `artifacts/clafact_final_completion_202608/issue_group_harness/claim_issue_master.csv`
- Modify: `artifacts/clafact_final_completion_202608/issue_group_harness/group_summary.csv`

**Step 1: Run focused and full automated tests**

Run:

```bash
python -m pytest tests/unit/test_issue_group_harness.py tests/unit/test_issue_group_harness_cli.py tests/integration/test_issue_group_executor.py -v
python -m pytest -q
```

Expected: all tests PASS.

**Step 2: Run one bounded context sample**

Run `CONTEXT` with `--limit 20` and an explicit run identifier. This execution must stop after re-admission and must not call KOSIS for claims that remain unadmitted.

**Step 3: Verify artifacts and traces**

Confirm 20 or fewer run rows, before/after fields on every row, no trace stage beyond the context policy ceiling, and reconciled group totals.

**Step 4: Commit and push**

```bash
git add core tools tests artifacts/clafact_final_completion_202608/issue_group_harness
git commit -m "feat: apply bounded issue-group improvement harness"
git push
```

Do not run all 1,542 Claims. The next full Registry execution remains locked until every required group gate passes.
