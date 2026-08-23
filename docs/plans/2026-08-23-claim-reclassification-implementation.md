# Claim Reclassification Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** CONTEXT 하네스가 공식 검증 대상과 안전한 검증 전 제외 Claim을 구분하고 CSV 및 묶음 진행표에 별도로 기록하게 한다.

**Architecture:** 새 `claim_disposition` 모듈이 Claim 원문과 12개 항목 결과를 보수적으로 분류한다. CONTEXT 실행기는 자식별 분류를 부모 상태로 합산하고, 기존 하네스는 재분류 결과를 별도 outcome과 CSV 열로 보존한다.

**Tech Stack:** Python 3.11+, Pydantic v2, pytest, 표준 `csv`/`dataclasses`

---

### Task 1: Claim 성격 판정기

**Files:**
- Create: `core/claim_disposition.py`
- Create: `tests/unit/test_claim_disposition.py`

**Step 1: Write the failing tests**

- 전망·예상·방침 문장은 `FORECAST_OR_POLICY`를 반환한다.
- 완성된 과거 사실형 수치 Claim은 `OFFICIAL_VERIFICATION_TARGET`을 반환한다.
- 검증할 지표값이 없는 문장은 `NO_VERIFIABLE_NUMERIC_ASSERTION`을 반환한다.
- 시점 등 필수 항목이 빠진 수치 Claim은 `SOURCE_CONTEXT_INSUFFICIENT`를 반환한다.

**Step 2: Run tests to verify RED**

Run: `python -m pytest tests/unit/test_claim_disposition.py -q`

Expected: module/function missing failure.

**Step 3: Implement minimal classifier**

Use stable enum-like literal values, explicit forecast/policy markers, targeted numeric expressions, and the existing 12-slot audit. Ambiguous cases must remain insufficient instead of excluded.

**Step 4: Run tests to verify GREEN**

Run: `python -m pytest tests/unit/test_claim_disposition.py -q`

Expected: all pass.

**Step 5: Commit**

Commit message: `feat: classify claim verification disposition`

### Task 2: CONTEXT 자식 및 부모 판정 연결

**Files:**
- Modify: `core/issue_group_executor.py`
- Create: `tests/unit/test_issue_group_reclassification.py`
- Modify: `tests/integration/test_issue_group_executor.py`

**Step 1: Write failing tests**

- 모든 자식이 제외 분류이면 부모는 `RECLASSIFIED`.
- 공식조회 가능 자식과 제외 자식만 섞이면 부모는 `PASS`.
- 원문 부족 자식이 하나라도 있으면 부모는 `HUMAN_REVIEW`.
- 공식조회는 CONTEXT 정책에서 호출되지 않는다.

**Step 2: Run tests to verify RED**

Run: `python -m pytest tests/unit/test_issue_group_reclassification.py tests/integration/test_issue_group_executor.py -q`

**Step 3: Implement minimal aggregation**

Add child `disposition`, `disposition_reason`, and `next_route`; compute parent status without converting exclusions into KOSIS success.

**Step 4: Run tests to verify GREEN**

Run the same command and expect all pass.

**Step 5: Commit**

Commit message: `feat: aggregate context claim reclassification`

### Task 3: CSV와 묶음 집계

**Files:**
- Modify: `core/issue_group_executor.py`
- Modify: `core/issue_group_harness.py`
- Modify: `tests/unit/test_issue_group_child_csv.py`
- Modify: `tests/unit/test_issue_group_summary_update.py`
- Create: `tests/unit/test_issue_group_reclassification_csv.py`

**Step 1: Write failing tests**

- 부모 실행 CSV와 자식 CSV에 `재분류결과`, `재분류사유`, `다음경로`가 기록된다.
- `RECLASSIFIED`는 재분류 완료 수에만 포함된다.
- `PASS`는 공식조회 진입 수에 포함된다.
- 남은 수는 두 완료 종류를 제외해 계산한다.

**Step 2: Run tests to verify RED**

Run: `python -m pytest tests/unit/test_issue_group_* -q`

**Step 3: Implement minimal CSV changes**

Extend run comparison and summary headers while keeping existing columns for compatibility.

**Step 4: Run tests to verify GREEN**

Run the same command and expect all pass.

**Step 5: Commit**

Commit message: `feat: record reclassification outcomes in csv`

### Task 4: 동일 20건 오프라인 재평가

**Files:**
- Update: `artifacts/clafact_final_completion_202608/issue_group_harness/claim_issue_master.csv`
- Update: `artifacts/clafact_final_completion_202608/issue_group_harness/group_summary.csv`
- Create: `artifacts/clafact_final_completion_202608/issue_group_harness/runs/context-004-reclassified.csv`
- Create: `artifacts/clafact_final_completion_202608/issue_group_harness/runs/context-004-reclassified_children.csv`

**Step 1: Reuse saved Structured Output**

Re-evaluate `context-002-time.jsonl` plus the final `context-003-target.jsonl` override. Do not call OpenAI or KOSIS.

**Step 2: Validate bounded scope**

Assert exactly the same first 20 parent Claim IDs and `official_lookup_attempted=false`.

**Step 3: Record CSV**

Write separate official-entry, reclassified, and remaining counts.

**Step 4: Run focused and full tests**

Run focused issue-group tests, then `python -m pytest -q`. Report any pre-existing missing-artifact failures separately.

**Step 5: Commit and push**

Commit message: `data: record first context reclassification results`

