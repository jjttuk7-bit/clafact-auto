# Direct Value Sign Direction Preservation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 직접값 381건의 원문 대상 숫자에 연결된 흑자·적자 및 증가·감소 방향을 결정론적으로 보존하고 통합 파이프라인에 반영한다.

**Architecture:** `core/source_sign_direction.py`가 원문 대상 위치와 지표·역할을 사용해 방향·극성·계산용 부호값을 판정한다. `tools/build_direct_value_sign_direction_audit.py`가 기존 381건 CSV를 결과 CSV와 누적 보강 JSONL로 변환한다. 통합 파이프라인은 확정된 방향 슬롯을 실행용 Claim에 보강하고, 애매하거나 역할이 충돌한 Claim은 공식조회 전에 정확한 구조화 사유로 중단한다.

**Tech Stack:** Python 표준 라이브러리, Pydantic v2, pytest

---

### Task 1: 대상 위치 기반 방향·극성 판정

**Files:**
- Create: `core/source_sign_direction.py`
- Create: `tests/unit/test_source_sign_direction.py`
- Create: `tests/unit/test_source_sign_direction_regressions.py`

1. 감소·증가·흑자·적자의 정상 사례 시험을 작성한다.
2. 문장 뒤쪽 다른 숫자의 방향으로 오염된 실제 사례 시험을 작성한다.
3. `증가폭 32만7000명`과 `3686만명을 정점으로 하락`의 경계 시험을 작성한다.
4. 시험 실패를 확인한다.
5. 대상 span과 같은 절의 방향만 연결하는 최소 판정기를 구현한다.
6. 원래 값과 별도 signed_target_value가 함께 보존되는지 시험한다.

### Task 2: 통합 파이프라인 보강

**Files:**
- Modify: `core/unified_claim_pipeline.py`
- Test: `tests/unit/test_sign_direction_pipeline.py`

1. 원문에서 회복한 direction이 기존 condition의 다른 키를 보존하며 병합되는 실패시험을 작성한다.
2. 무역수지 polarity와 계산용 부호값이 보강자료에 남는 시험을 작성한다.
3. 방향 모호·역할 충돌 상태가 공식 서비스 호출 전에 중단되는 시험을 작성한다.
4. 시험 실패를 확인한 뒤 최소 구현하고 관련 회귀시험을 통과시킨다.

### Task 3: 381건 실행과 기록

**Files:**
- Create: `tools/build_direct_value_sign_direction_audit.py`
- Create: `tests/unit/test_build_direct_value_sign_direction_audit.py`
- Create: `deliverables/CLAFACT_AUTO_8번_1단계_부호방향보존_20260825.csv`
- Create: `deliverables/CLAFACT_AUTO_8번_1단계_부호방향보존_파이프라인보강_20260825.jsonl`
- Create: `deliverables/CLAFACT_AUTO_8번_1단계_부호방향보존_실행이력_20260825.csv`
- Create: `deliverables/CLAFACT_AUTO_8번_1단계_부호방향보존_검증이력_20260825.csv`
- Create: `deliverables/CLAFACT_AUTO_8번_1단계_부호방향보존_결과보고_20260825.txt`
- Create: `deliverables/CLAFACT_AUTO_8번_체크리스트상태_1단계5완료_20260825.json`

1. 381건 입력·출력·고유 Claim 계수를 검증하는 실패시험을 작성한다.
2. 모든 부호 적용 결과에 방향·극성, signed_target_value, 원문 근거 위치가 있는지 검증한다.
3. 결과 CSV와 누적 보강 JSONL을 생성한다.
4. 실제 사례를 상태별로 전수 대조하고 과도한 자동 교정을 회귀시험에 추가한다.
5. 관련 회귀시험과 전체 단위시험을 실행한다.
6. 성공·실패·미평가 원인과 적용 범위를 보고서와 이력에 기록한다.
7. 검증된 코드와 산출물만 커밋하고 현재 원격 브랜치에 푸시한다.
