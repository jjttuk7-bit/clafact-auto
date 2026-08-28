# Direct-Value Hard-Guard 94 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Classify all 94 direct-value coordinate failures by evidence-backed primary cause, add only safe reusable coordinate rules to the canonical pipeline, rerun the same 94 Claims through live official APIs, and publish an auditable before/after evaluation.

**Architecture:** Reuse the frozen 176-Claim query specs and canonical live results to derive an immutable 94-Claim scope. A deterministic classifier combines source-grounding status, Claim slots, official candidate metadata, and Hard Guard diagnostics. General normalization changes are made only in existing core modules, followed by a live rerun through `tools.run_clafact_pipeline`; an evaluator joins before and after rows without changing official verdict semantics.

**Tech Stack:** Python 3.12+, Pydantic v2, pytest, KOSIS official Catalog/Metadata/Value APIs, CSV/JSONL audit artifacts.

---

### Task 1: Freeze and test the exact 94-Claim scope

**Files:**
- Create: `core/direct_value_coordinate_94_scope.py`
- Create: `tests/unit/test_direct_value_coordinate_94_scope.py`
- Create: `tools/build_direct_value_coordinate_94_scope.py`

**Step 1: Write the failing tests**

Test that the builder selects exactly the 94 rows whose `최종실패단계` is `필수 조건 검사`, preserves all 94 unique Claim IDs, and rejects duplicate or incomplete input.

**Step 2: Run tests and confirm RED**

Run: `python -m pytest tests/unit/test_direct_value_coordinate_94_scope.py -q`

Expected: FAIL because the scope module does not exist.

**Step 3: Implement the minimal immutable scope builder**

Store Claim ID, source hash, before reason, query spec, candidate diagnostic reference, and input hashes. Do not select by Claim ID.

**Step 4: Run tests and confirm GREEN**

Run: `python -m pytest tests/unit/test_direct_value_coordinate_94_scope.py -q`

Expected: PASS.

### Task 2: Classify one primary cause and supporting causes for all 94 Claims

**Files:**
- Create: `core/direct_value_coordinate_failure_classifier.py`
- Create: `tests/unit/test_direct_value_coordinate_failure_classifier.py`
- Modify: `tools/build_direct_value_coordinate_94_scope.py`

**Step 1: Write failing tests for cause boundaries**

Cover at least:

- wrong indicator/value role is `CLAIM_STRUCTURE_ERROR` before coordinate causes;
- non-KOSIS source scope is `NON_KOSIS_OFFICIAL_ROUTE`;
- same-family scale mismatch is `UNIT_COORDINATE_GAP`;
- different currencies are not treated as a scale mismatch;
- period/frequency conflict, region conflict, dimension conflict, metadata gap, and evidence ambiguity remain distinct;
- every classification contains evidence fields and a reusable rule family.

**Step 2: Run tests and confirm RED**

Run: `python -m pytest tests/unit/test_direct_value_coordinate_failure_classifier.py -q`

Expected: FAIL because the classifier does not exist.

**Step 3: Implement deterministic classification**

Use stable Claim fields, source-grounding audit, candidate metadata and `hard_guard_best_reject_*` diagnostics. Never use Claim IDs, article IDs or full-sentence equality.

**Step 4: Run tests and confirm GREEN**

Run both Task 1 and Task 2 tests. Assert exactly 94 classified rows and no empty primary causes.

### Task 3: Add safe measurement-scale normalization

**Files:**
- Modify: `core/unit_normalizer.py`
- Modify: `tests/unit/test_unit_normalizer.py`
- Modify: `tests/unit/test_catalog_search_and_hard_guard.py`

**Step 1: Write failing tests**

Add same-family tests for KRW (`원/만원/억원/조원`), USD (`달러/천달러/만달러/억달러`), people, households and supported quantities. Add negative tests proving KRW and USD are incompatible and percentages are not percentage points.

**Step 2: Run tests and confirm RED**

Run: `python -m pytest tests/unit/test_unit_normalizer.py tests/unit/test_catalog_search_and_hard_guard.py -q`

**Step 3: Implement minimal unit families and scale factors**

Do not introduce exchange-rate conversion. Keep all conversions deterministic in Python.

**Step 4: Run tests and confirm GREEN**

Run the same tests and relevant evidence resolver tests.

### Task 4: Normalize national region and period/frequency aliases safely

**Files:**
- Modify: `core/member_code_mapper.py`
- Modify: `core/evidence_resolver_impl.py`
- Modify: `core/kosis_query_spec_compiler.py`
- Modify: `tests/unit/test_member_code_region_aliases.py`
- Modify: `tests/unit/test_evidence_resolver.py`
- Modify: `tests/unit/test_kosis_query_spec_compiler.py`

**Step 1: Write failing positive and negative tests**

Cover `한국/대한민국/전국`, source-grounded national `국내`, official province spelling, `Y/M/Q`, Korean aliases and cumulative ranges. Prove that ambiguous `전체`, foreign countries, relative time without article date, and unsupported half-year/decade formats do not auto-resolve.

**Step 2: Run tests and confirm RED**

**Step 3: Implement canonical normalization once**

Keep region aliasing in the member-code layer and period/frequency mapping in the query/evidence layers. Do not relax Hard Guard globally.

**Step 4: Run tests and confirm GREEN**

### Task 5: Improve exact official dimension-member binding

**Files:**
- Modify: `core/member_code_mapper.py`
- Modify: `core/evidence_resolver_impl.py`
- Modify: `core/hard_guard_impl.py` only if a failing test proves the current rejection is incorrect
- Create: `tests/unit/test_direct_value_coordinate_common_bindings.py`

**Step 1: Write failing tests from reusable metadata shapes**

Cover industry, product, age/population, education and total-member aliases. Require unique official member-code resolution and reject ambiguous or missing official members.

**Step 2: Run tests and confirm RED**

**Step 3: Implement bounded aliases and exact uniqueness checks**

Aliases must be general label normalization rules. Do not add table IDs, Claim IDs or full source sentences.

**Step 4: Run tests and confirm GREEN**

### Task 6: Build the 94-Claim rerun Registry and before/after evaluator

**Files:**
- Create: `core/direct_value_coordinate_94_evaluation.py`
- Create: `tests/unit/test_direct_value_coordinate_94_evaluation.py`
- Create: `tools/compile_direct_value_coordinate_94_results.py`

**Step 1: Write failing tests**

Require exactly 94 unique output rows. Preserve before stage/reason, primary and supporting causes, applied common rule, after stages, official coordinate/provenance, strict official completion and before/after movement.

**Step 2: Run tests and confirm RED**

**Step 3: Implement strict merge and completeness checks**

Official completion requires one-to-one evidence/provenance keys, API source, URL, response hash, retrieval time and verified publication.

**Step 4: Run tests and confirm GREEN**

### Task 7: Execute the same 94 Claims through live official APIs

**Files:**
- Create: `artifacts/direct_value_coordinate_94_20260828/`
- Create: `deliverables/CLAFACT_AUTO_직접값94_공통좌표규칙_20260828/`

**Step 1: Build the immutable scope and input manifest**

Run the scope builder and assert 94/94 coverage, unique IDs, source hashes and code/data hashes.

**Step 2: Run the canonical pipeline**

Run `tools.run_clafact_pipeline` with the 94-Claim Registry, actual KOSIS credentials, stored-slot mode and no LLM-generated official values.

**Step 3: Verify official execution evidence**

Confirm Catalog, Metadata, Value and Publication attempts are recorded. Retry operational failures only; never reuse stale results as a new live run.

**Step 4: Compile the before/after CSV and report**

Record all 94 rows, primary-cause counts, rule-family counts, stage movements, strict verdict increments and remaining failure reasons.

### Task 8: Verify, review, commit and push

**Files:**
- Modify as required by review findings only.

**Step 1: Run focused tests**

Run all new tests plus unit, guard, evidence resolver and canonical pipeline tests.

**Step 2: Run the full test suite**

Exclude only tests whose external Registry artifact is demonstrably absent, and report them explicitly.

**Step 3: Verify artifacts**

Check 94 unique evaluation rows, hashes, no API secrets, official evidence completeness, and before/after totals.

**Step 4: Review the staged diff**

Reject any Claim-ID/table-ID special casing, guard relaxation without evidence, fake official values, or completion overcount.

**Step 5: Commit and push**

Commit implementation and artifacts, verify fast-forward status, push the branch and `main`, and verify the remote SHA.

