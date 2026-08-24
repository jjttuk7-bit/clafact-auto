# Remaining Claim Subclassification Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 남은 1,518개 Claim을 결정론적인 세부 문제 유형으로 나누고 통합 원장과 요약에 영구 기록하며, 다음에 실행할 첫 대표 20건을 확정한다.

**Architecture:** 새 순수 함수 모듈이 원장의 최신 단계·사유, 12개 항목 누락, 원문 표현을 이용해 Claim마다 하나의 세부 유형을 부여한다. 통합 원장 생성기는 병합이 끝난 뒤 전체 행을 세부 분류하고, 유형별 남은 건수와 대표 실행 묶음을 요약 JSON에 기록한다.

**Tech Stack:** Python 3.12, dataclasses, csv/json, pytest

---

### Task 1: 세부 분류 규칙

**Files:**
- Create: `core/claim_issue_subclassification.py`
- Create: `tests/unit/test_claim_issue_subclassification.py`

1. 완료 Claim, 최신 사유 우선, 문맥 기록 주장, 여러 수치, 상대기간, 슬롯 누락을 검증하는 실패 테스트를 작성한다.
2. `python -m pytest tests/unit/test_claim_issue_subclassification.py -q`를 실행해 기능 부재로 실패하는지 확인한다.
3. 하나의 행을 하나의 세부 유형·쉬운 설명·해결방법으로 바꾸는 최소 함수를 구현한다.
4. 필수 조건·공식 경로·의미·좌표·값·발표·계산 유형 테스트를 추가하고 실패를 확인한다.
5. 모든 유형을 결정론적으로 분류하는 최소 코드를 구현하고 단위 테스트를 통과시킨다.

### Task 2: 우선순위와 대표 20건

**Files:**
- Modify: `core/claim_issue_subclassification.py`
- Modify: `tests/unit/test_claim_issue_subclassification.py`

1. 남은 유형의 건수 내림차순으로 우선순위를 매기고 Claim 번호순 최대 20건에만 대표 실행 묶음을 지정하는 실패 테스트를 작성한다.
2. 테스트가 예상 이유로 실패하는지 확인한다.
3. `annotate_issue_subclasses`와 요약 함수를 최소 구현한다.
4. 완료 Claim 제외, 동률 정렬, 중복 없는 대표 선정 테스트를 통과시킨다.

### Task 3: 통합 원장 영구 연결

**Files:**
- Modify: `core/consolidated_claim_ledger.py`
- Modify: `tools/build_consolidated_claim_ledger.py`
- Modify: `tests/unit/test_consolidated_claim_ledger.py`
- Modify: `tests/unit/test_build_consolidated_claim_ledger_cli.py`

1. 통합 결과에 다섯 개 세부 분류 열이 존재하는 실패 테스트를 작성한다.
2. 요약 JSON에 `remaining_by_subtype`, `subclassified_remaining_count`, `first_execution_batch`가 존재하는 실패 테스트를 작성한다.
3. 두 실패가 새 기능 부재 때문인지 확인한다.
4. 병합 후 분류 함수 호출과 요약 생성을 연결한다.
5. 관련 단위 테스트를 통과시킨다.

### Task 4: 실제 1,542행 원장 재생성

**Files:**
- Modify: `artifacts/clafact_final_completion_202608/CLAFACT_1542_통합진행원장.csv`
- Modify: `artifacts/clafact_final_completion_202608/CLAFACT_1542_통합진행원장_요약.json`

1. 기존 1,542행 원장을 안전한 임시 입력으로 사용해 분류가 포함된 새 원장을 만든다.
2. 행 수 1,542, 고유 Claim 1,542, 완료 24, 남음 1,518을 확인한다.
3. 남은 Claim의 세부 유형 누락 0과 유형별 합계 1,518을 확인한다.
4. 대표 묶음 Claim이 유형마다 최대 20건이고 중복 0인지 확인한다.
5. 같은 입력을 다시 처리한 임시 결과와 내용 해시가 같은지 확인한다.

### Task 5: 회귀 검증과 첫 목표 완료

1. 신규·관련 단위 테스트를 실행한다.
2. `python -m pytest -q` 전체 회귀 테스트를 실행하고 기존 외부 자료 누락 실패와 새 실패를 구분한다.
3. `git diff --check`를 실행한다.
4. 첫 실행 묶음의 유형·건수·Claim 번호를 요약한다.
5. 코드·테스트·원장·요약을 커밋하고 사용자가 승인한 원격 브랜치에 푸시한다.

