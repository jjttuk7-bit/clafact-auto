# Employment Change Amount Reclassification Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 잘못 `DIRECT_VALUE`로 저장된 고용 증감액 Claim을 원문 근거로 안전하게 `DIFFERENCE`로 재분류하고, 현재·비교 기간 KOSIS 공식값을 조회해 Python 계산과 감사 CSV까지 완성한다.

**Architecture:** 대상 수치 조각을 받는 기존 `recover_validated_claim`에 보수적인 일반 규칙을 추가하고, 선택된 Registry 레코드만 교정하는 bounded 도구를 둔다. 교정 이후에는 별도 검증기를 만들지 않고 기존 unified pipeline과 v3 official engine을 그대로 사용한다.

**Tech Stack:** Python 3.12+, Pydantic v2, pytest, 기존 KOSIS adapters, CSV/JSONL 묶음 실행 산출물.

---

### Task 1: 증감액 재분류 계약을 테스트로 고정

**Files:**
- Modify: `tests/unit/test_validated_claim_recovery.py`
- Modify: `tests/unit/test_cpi_dynamic_evidence.py`

**Step 1: 실패 테스트 작성**

- 대상 수치 조각과 원문에 전년 대비 감소가 명확한 인원 Claim은 `DIRECT_VALUE`에서 `DIFFERENCE`로 바뀐다.
- `comparison.operand_source`는 `OFFICIAL_EVIDENCE`가 된다.
- 다른 숫자의 감소 표현이 섞인 문장에서 직접값 Claim은 바뀌지 않는다.
- 현재 공식값이 과거 공식값보다 작을 때 계산된 음수 차이를 기사에 적힌 양수 감소 크기와 안전하게 비교한다.
- 계산 방향이 원문 방향과 반대면 MATCH가 되지 않는다.

**Step 2: RED 확인**

Run: `python -m pytest -q tests/unit/test_validated_claim_recovery.py tests/unit/test_cpi_dynamic_evidence.py`

### Task 2: 최소 재분류와 방향 계산 구현

**Files:**
- Modify: `core/validated_claim_recovery.py`
- Modify: `core/dynamic_kosis_verifier.py`

**Step 1: 최소 구현**

- 대상 수치 조각, 변화 비교 방식, 방향, 원문 변화 표현을 모두 검사한다.
- 조건이 맞는 경우에만 `DIFFERENCE`와 `OFFICIAL_EVIDENCE`를 설정한다.
- 모든 `DIFFERENCE` 계산에서 공식값의 부호와 Claim 방향을 먼저 검증한 뒤 기사 변화량 크기로 변환한다.

**Step 2: GREEN 확인**

Task 1의 테스트를 다시 실행해 실패가 없어야 한다.

### Task 3: 선택 Registry 재분류 도구와 CSV 계약 구현

**Files:**
- Create: `tools/reclassify_change_amount_group.py`
- Create: `tests/unit/test_reclassify_change_amount_group.py`

**Step 1: 실패 테스트 작성**

- 명시한 Claim ID만 처리하고 무제한 실행을 거부한다.
- 원본 Registry는 바꾸지 않고 작은 교정 Registry를 생성한다.
- CSV에 Claim ID, 대상 수치 조각, 변경 전후 계산 방식, 비교 방식, 방향, 상태, 변경 사유를 기록한다.
- 실제로 바뀌지 않은 Claim은 공식 재실행 대상으로 내보내지 않는다.

**Step 2: RED 확인 후 최소 구현**

Run: `python -m pytest -q tests/unit/test_reclassify_change_amount_group.py`

**Step 3: GREEN 확인**

동일 명령을 다시 실행해 실패가 없어야 한다.

### Task 4: 2건만 실제 KOSIS 재검증

**Files:**
- Runtime output: `artifacts/clafact_final_completion_202608/employment_change_amount_2_live_20260823/`
- Runtime CSV: reclassification before/after, official-stage result, group gate

**Step 1: 입력 고정**

기존 고용 묶음에서 승인된 두 Claim ID만 선택한다. 원본 Registry는 변경하지 않는다.

**Step 2: 재분류 실행**

도구로 교정 Registry와 개선 전후 CSV를 생성하고 두 건 모두 `DIFFERENCE`인지 확인한다.

**Step 3: 실제 공식 API 실행**

교정된 2건만 bounded unified pipeline으로 실행한다. Catalog, metadata, 두 Evidence 좌표, 두 공식값, 공표정보, Python 계산, Verdict trace를 보존한다.

**Step 4: 묶음 판정**

두 건 각각에서 재분류 성공, 공식값 두 개 수집, Python 차이 계산, 단계별 상태와 출처가 기록됐는지 CSV gate로 판정한다. 공식 조회 실패는 실제 단계 reason code로 보존한다.

### Task 5: 검증·리뷰·커밋·푸시

**Step 1: 집중 테스트**

Run: `python -m pytest -q tests/unit/test_validated_claim_recovery.py tests/unit/test_cpi_dynamic_evidence.py tests/unit/test_reclassify_change_amount_group.py`

**Step 2: 전체 단위 테스트**

Run: `python -m pytest tests/unit -q --ignore=tests/unit/test_goal_completion_audit.py`

**Step 3: 정적 확인**

Run: `git diff --check`

**Step 4: 변경 검토**

Critical/Important 문제가 없어질 때까지 수정하고 관련 회귀 테스트를 다시 실행한다.

**Step 5: 커밋·푸시**

Commit message: `feat: reclassify employment change amounts`

