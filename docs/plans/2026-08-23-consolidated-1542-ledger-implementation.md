# Consolidated 1,542 Claim Ledger Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 분산된 결과 파일을 최신 우선 규칙으로 병합하여 항상 1,542행인 단일 진행 원장을 재생성한다.

**Architecture:** 형식별 결과 어댑터가 공통 `LedgerUpdate`를 만들고, 결정론적 병합기가 부모 Claim별 최신 결과를 선택한다. CLI는 원본 원장과 결과 루트를 입력받아 통합 CSV와 요약 JSON을 원자적으로 쓴다.

**Tech Stack:** Python 3.12, dataclasses, csv/json, pytest

---

### Task 1: 공통 병합 계약

**Files:**
- Create: `core/consolidated_claim_ledger.py`
- Create: `tests/unit/test_consolidated_claim_ledger.py`

1. 1,542행 대신 작은 fixture 원장으로 식별자 보존 테스트를 작성한다.
2. 같은 Claim의 이전·최신 결과 중 최신만 현재 결과로 선택하는 실패 테스트를 작성한다.
3. 자식 Claim 여러 건을 부모 한 행에 묶는 실패 테스트를 작성한다.
4. 알 수 없는 Claim과 동일 시각 충돌을 거부하는 실패 테스트를 작성한다.
5. 테스트가 기능 부재로 실패하는지 확인한다.
6. 최소 병합 코드를 구현하고 테스트를 통과시킨다.

### Task 2: 결과 형식 어댑터

**Files:**
- Modify: `core/consolidated_claim_ledger.py`
- Modify: `tests/unit/test_consolidated_claim_ledger.py`

1. 하네스 실행 CSV 어댑터 테스트를 작성한다.
2. 기록 비교 CSV 어댑터 테스트를 작성한다.
3. 다중 Claim 결과 CSV 어댑터 테스트를 작성한다.
4. 공식 단계 결과와 완료 판정 CSV 어댑터 테스트를 작성한다.
5. Registry JSONL 자식→부모 연결 테스트를 작성한다.
6. 각 테스트를 먼저 실패시킨 뒤 최소 구현으로 통과시킨다.

### Task 3: 재생성 CLI

**Files:**
- Create: `tools/build_consolidated_claim_ledger.py`
- Create: `tests/unit/test_build_consolidated_claim_ledger_cli.py`

1. 기존 출력 덮어쓰기 금지와 명시적 `--replace` 테스트를 작성한다.
2. 출력 1,542행·고유 식별자·결과 출처 기록 테스트를 작성한다.
3. 요약 JSON의 입력 수·반영 Claim 수·오류 수 테스트를 작성한다.
4. CLI를 구현하고 관련 테스트를 통과시킨다.

### Task 4: 실제 통합 원장 생성

**Files:**
- Create: `artifacts/clafact_final_completion_202608/CLAFACT_1542_통합진행원장.csv`
- Create: `artifacts/clafact_final_completion_202608/CLAFACT_1542_통합진행원장_요약.json`

1. 전체 결과 루트에서 인식 가능한 실행 결과를 수집한다.
2. 통합 CLI를 실행한다.
3. 1,542행·식별자 고유성·최신 고용 결과 반영을 검사한다.
4. 같은 입력으로 두 번째 임시 출력을 만들어 해시가 동일한지 확인한다.

### Task 5: 회귀 검증과 저장

1. 신규 단위 테스트를 실행한다.
2. 전체 회귀 테스트를 실행한다.
3. `git diff --check`와 통합 파일 통계를 확인한다.
4. 이번 변경만 커밋하고 작업 브랜치에 푸시한다.
