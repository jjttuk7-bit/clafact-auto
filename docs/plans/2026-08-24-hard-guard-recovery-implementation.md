# Hard Guard 193건 원인 기록 및 공통 해결 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** `HARD_GUARD_ALIAS`로 뭉뚱그려진 193건의 실제 후보 탈락 조건을 보존하고, 가장 큰 반복 원인을 통합 엔진에서 일반화해 같은 193건만 재실행한다.

**Architecture:** `OfficialEvidenceService`가 실시간 KOSIS 메타데이터로 구성된 최종 후보 각각에 기존 Hard Guard를 적용하고, 탈락 코드별 개수를 안전한 정수 진단값으로 보존한다. CSV와 통합 원장은 이 값을 사람이 읽는 원인으로 기록한다. 원인 집계 후에만 가장 큰 반복 원인의 정규화 규칙을 공식 메타데이터 확인 뒤 적용하며, 단위·주기·기간·지역 조건은 우회하지 않는다.

**Tech Stack:** Python 3.12, Pydantic v2, pytest, KOSIS 공식 API, Streamlit 공통 Canonical Pipeline

---

### Task 1: 후보별 Hard Guard 탈락 코드 집계

**Files:**
- Create: `core/hard_guard_diagnostics.py`
- Test: `tests/unit/test_hard_guard_diagnostics.py`

**Step 1:** 실제 `KosisCandidateSchema` 여러 개에서 `FREQUENCY_CONFLICT`, `UNIT_CONFLICT`, `DIMENSION_MEMBER_CONFLICT`와 통과 후보 수가 각각 집계되길 기대하는 실패 테스트를 작성한다.

**Step 2:** `pytest tests/unit/test_hard_guard_diagnostics.py -q`를 실행해 모듈 부재로 실패함을 확인한다.

**Step 3:** 기존 `apply_hard_guard`만 호출하여 `hard_guard_candidate_count`, `hard_guard_passed_count`, `hard_guard_reject_<CODE>` 정수 값을 반환하는 최소 함수를 구현한다.

**Step 4:** 같은 시험을 다시 실행해 통과를 확인한다.

### Task 2: 통합 엔진 결과에 탈락 코드 보존

**Files:**
- Modify: `core/official_evidence_service.py`
- Test: `tests/unit/test_official_evidence_service.py`

**Step 1:** 후보 선택 이후의 후보에 대한 탈락 코드 집계가 `catalog_diagnostics`에 포함되길 기대하는 실패 테스트를 작성한다.

**Step 2:** 해당 단일 시험을 실행해 새 진단값 부재로 실패함을 확인한다.

**Step 3:** `OfficialEvidenceService.resolve`에서 후보 선택 직후 집계 함수를 호출하고 기존 API 시도 횟수와 함께 보존한다. 검증 순서와 후보 목록은 변경하지 않는다.

**Step 4:** 관련 시험을 실행해 통과를 확인한다.

### Task 3: CSV와 통합 원장에 실제 탈락 원인 기록

**Files:**
- Modify: `core/official_run_csv.py`
- Modify: `core/consolidated_claim_ledger.py`
- Modify: `core/claim_issue_subclassification.py`
- Test: `tests/unit/test_official_run_csv.py`
- Test: `tests/unit/test_consolidated_claim_ledger.py`
- Test: `tests/unit/test_claim_issue_subclassification.py`

**Step 1:** 공식 실행 CSV의 `조건검사탈락사유`와 통합 원장의 `최신조건탈락사유`에 실제 코드와 개수가 기록되길 기대하는 실패 테스트를 작성한다.

**Step 2:** 새 열이 없어 실패하는 것을 확인한다.

**Step 3:** 직렬화된 `catalog_diagnostics`에서 `hard_guard_reject_` 접두어만 추출해 기록한다. `TIME_NOT_AVAILABLE/FREQUENCY_CONFLICT`, `UNIT_CONFLICT`, 지역·연령·성별·차원 충돌, `METADATA_INCOMPLETE`를 각각 기간·단위·차원·공식 구조 문제로 재분류한다.

**Step 4:** 세 시험 파일을 실행해 통과를 확인한다.

### Task 4: 193건만 원인 진단 재실행

**Files:**
- Create: `artifacts/clafact_final_completion_202608/hard_guard_193_input_20260824.jsonl`
- Create: `artifacts/clafact_final_completion_202608/hard_guard_193_diagnostic_20260824/`

**Step 1:** 통합 원장의 `세부문제유형=HARD_GUARD_ALIAS` Claim ID와 Registry를 결합해 정확히 193개 입력을 만든다. 중복·누락·범위 밖 Claim을 거부한다.

**Step 2:** 입력 수가 정확히 193인지 확인한다.

**Step 3:** `tools/run_clafact_pipeline.py`의 Canonical Pipeline으로 저장 슬롯을 사용해 193건만 실행한다.

**Step 4:** 탈락 코드별 Claim 수, 공식값 조회 도달 수, 판정 수를 집계하고 193건 외 결과가 없는지 확인한다.

### Task 5: 가장 큰 실제 반복 원인 하나의 일반 해결

**Files:**
- Modify: 원인 집계로 확인된 단일 Core 정규화 모듈
- Modify: 공식 메타데이터 기반 별칭 자료가 필요한 경우 해당 버전 파일
- Test: 원인에 대응하는 단위 시험 및 통합 시험

**Step 1:** Task 4에서 가장 많은 Claim에 공통되는 단일 탈락 코드를 선택하고, 대표 지표와 반대 사례를 포함한 실패 테스트를 먼저 작성한다.

**Step 2:** 테스트가 현재 코드에서 같은 탈락 코드로 실패하는지 확인한다.

**Step 3:** 공식 메타데이터에 대상 명칭이 하나만 존재할 때만 적용되는 최소 정규화 규칙을 구현한다. Claim ID와 원문 전체 일치는 사용하지 않는다.

**Step 4:** 단위·통합 시험과 관련 회귀 시험을 통과시킨다.

### Task 6: 개선 후 193건 전체 재실행과 원장 반영

**Files:**
- Create: `artifacts/clafact_final_completion_202608/hard_guard_193_after_20260824/`
- Modify: `artifacts/clafact_final_completion_202608/CLAFACT_1542_통합진행원장.csv`

**Step 1:** 동일한 193개 입력과 동일한 Canonical Pipeline으로 개선 후 실행한다.

**Step 2:** 개선 전후 공식값 조회 도달 수, 판정 수, 단계 이동 수, 남은 탈락 코드별 수를 비교한다.

**Step 3:** 193건 결과만 통합 원장에 누적하고 다른 1,349행의 최신 실행 정보가 바뀌지 않았음을 확인한다.

**Step 4:** 해결된 패턴을 대시보드와 동일한 `verify_dashboard_article` 경계로 재현해 공식값·판정·근거가 같은지 확인한다.

**Step 5:** 관련 시험과 전체 회귀 시험을 실행한 뒤 코드와 감사 가능한 결과를 분리 커밋한다.
