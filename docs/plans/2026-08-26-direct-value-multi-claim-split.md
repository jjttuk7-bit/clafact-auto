# Direct Value Multi-Claim Split Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 숫자 역할이 안전한 직접값 부모 360건에서 복수 통계 Claim을 빠짐없이 자식 Claim으로 분리하고 자식별 12슬롯·재Admission·공식 엔진 경로를 보존한다.

**Architecture:** 원문 기반 통계 수치 탐색을 먼저 교정하고, 통계 수치가 둘 이상이면 확정 대상값 경로보다 Structured Output 그룹화를 먼저 실행한다. Python 검증기가 그룹의 완전성과 원문 위치를 검증하며, 자식 Claim은 기존 unified pipeline과 v3 official engine에 그대로 재진입한다. 360건 실행기는 승인된 외부 전송 상한 236개를 강제하고 부모·자식 결과를 CSV와 JSONL로 기록한다.

**Tech Stack:** Python 3.12+, Pydantic v2, OpenAI Structured Output adapter, pytest, KOSIS v3 official engine

---

### Task 1: 통계 수치 탐색 경계 교정

**Files:**
- Modify: `core/targeted_claim_splitter.py`
- Modify: `tests/unit/test_targeted_claim_splitter.py`

1. `10개월`을 `10개`로 탐색하지 않는 실패시험을 작성한다.
2. `116.38` 물가지수와 `2.1%` 상승률을 각각 원문 span과 함께 탐색하는 실패시험을 작성한다.
3. `10명 중 1명`, 환산금액, `%포인트`가 긴 단위 그대로 보존되는 시험을 작성한다.
4. 실패가 기존 탐색기 경계와 지수 수준 미지원 때문인지 확인한다.
5. 긴 단위 우선·단위 경계·명시적 지수 문맥만 처리하는 최소 구현을 작성한다.
6. 신규 시험과 기존 targeted splitter·group normalizer 시험을 실행한다.
7. 변경을 커밋한다.

### Task 2: 복수 그룹화를 부모 대표값 차단보다 먼저 실행

**Files:**
- Modify: `core/admission_recovery_v3.py`
- Modify: `core/unified_claim_pipeline.py`
- Modify: `tests/unit/test_target_grounding_pipeline.py`
- Modify: `tests/unit/test_admission_recovery_v3_grouping.py`

1. 확정 대상값이 있어도 두 독립 지표가 두 자식으로 생성되는 실패시험을 작성한다.
2. 부모 지표·단위 상태가 충돌이어도 복수 그룹화 후 정상 자식이 공식 서비스까지 도달하는 실패시험을 작성한다.
3. 모호한 그룹은 공식 서비스 호출 0건인 시험을 유지·확장한다.
4. 단일 통계 수치 확정 대상은 기존 regrouping 우회 동작을 유지하는 시험을 작성한다.
5. `recover_registry_record_v3`에서 복수 수치 그룹화를 prelinked target보다 먼저 배치한다.
6. `verify_registry_record`에서 복수 그룹화 대상은 부모 지표·단위 차단을 자식 생성 전 적용하지 않도록 최소 분기를 추가한다.
7. 신규 시험과 unified pipeline 관련 회귀시험을 실행한다.
8. 변경을 커밋한다.

### Task 3: 360건 승인 범위 실행기와 감사 산출물

**Files:**
- Create: `core/direct_value_multi_claim_scope.py`
- Create: `tools/run_direct_value_multi_claim_scope.py`
- Create: `tests/unit/test_direct_value_multi_claim_scope.py`
- Create: `tests/integration/test_direct_value_multi_claim_scope_pipeline.py`

1. 381건 입력에서 숫자 역할 안전 부모 360건을 정확히 선택하는 실패시험을 작성한다.
2. 외부 전송 대상이 236개를 넘으면 실행 전 실패하는 시험을 작성한다.
3. 단일 부모, 한 그룹 부모, 복수 그룹 부모, 모호 부모의 계수와 부모·자식 연결을 검증하는 시험을 작성한다.
4. 코드·자료 hash를 포함하는 체크포인트 resume 시험을 작성한다.
5. 최소 범위 선택기와 20건 단위 bounded runner를 구현한다.
6. 부모 CSV, 자식 CSV, 결과 JSONL, 공식 재입력 Registry JSONL을 원자적으로 기록한다.
7. 신규 단위·통합시험을 실행한다.
8. 변경을 커밋한다.

### Task 4: 실제 360건 실행과 완료 증거

**Files:**
- Create: `deliverables/CLAFACT_AUTO_8번_1단계_복수Claim분리_부모결과_20260826.csv`
- Create: `deliverables/CLAFACT_AUTO_8번_1단계_복수Claim분리_자식결과_20260826.csv`
- Create: `deliverables/CLAFACT_AUTO_8번_1단계_복수Claim분리_구조화결과_20260826.jsonl`
- Create: `deliverables/CLAFACT_AUTO_8번_1단계_복수Claim분리_공식재입력_20260826.jsonl`
- Create: `deliverables/CLAFACT_AUTO_8번_1단계_복수Claim분리_실행이력_20260826.csv`
- Create: `deliverables/CLAFACT_AUTO_8번_1단계_복수Claim분리_검증이력_20260826.csv`
- Create: `deliverables/CLAFACT_AUTO_8번_1단계_복수Claim분리_결과보고_20260826.txt`
- Create: `deliverables/CLAFACT_AUTO_8번_체크리스트상태_1단계7완료_20260826.json`

1. 사전 실행으로 입력 360건과 외부 전송 대상 수가 승인 상한 이하인지 확인한다.
2. 20건 단위 체크포인트로 Structured Output 그룹화와 자식 12슬롯 구조화를 실행한다.
3. 부모 수·생성 자식 수·부모 연결·수치 배정·중단 사유를 독립 대조한다.
4. 공식 재입력 Registry가 unified pipeline/v3 official engine이 읽을 수 있는지 검증한다.
5. 관련 회귀시험과 외부 기준자료 의존 시험을 제외한 전체 단위시험을 실행한다.
6. 성공·실패 원인과 적용 가능한 부모·자식 수를 결과 파일과 쉬운 용어 보고서에 기록한다.
7. 체크리스트는 모든 완료 기준이 실제로 통과한 경우에만 완료로 표시한다.
8. 검증된 산출물만 커밋하고 현재 원격 브랜치에 푸시한다.
