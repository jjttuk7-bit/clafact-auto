# Direct Value Numeric Role Gate Audit Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 직접값 381건의 기존 숫자 역할 안전장치를 통합 검증하고 Claim별 자동 처리 가능 여부와 차단 근거를 기록한다.

**Architecture:** `tools/build_direct_value_numeric_role_gate_audit.py`가 부호·방향 결과 CSV의 누적 보강자료를 읽고 원문 대상 상태·수준값 오인 상태·표현 위치를 다시 검증한다. 운영 파이프라인은 이미 `target_link_preverification_reason`과 `sign_direction_preverification_reason`으로 차단하므로 중복 Core 분류기를 만들지 않는다. 시험은 통합 결과와 기존 공식조회 전 중단 계약을 함께 검증한다.

**Tech Stack:** Python 표준 라이브러리, Pydantic v2, pytest

---

### Task 1: 통합 숫자 역할 안전판 산출기

**Files:**
- Create: `tools/build_direct_value_numeric_role_gate_audit.py`
- Create: `tests/unit/test_build_direct_value_numeric_role_gate_audit.py`

1. 안전 대상, 보호 역할 차단, 수준값 오인 차단 입력의 실패시험을 작성한다.
2. 시험이 모듈 부재로 실패하는지 확인한다.
3. 기존 상태와 원문 span을 재검증하는 최소 산출기를 구현한다.
4. 출력 합계·고유 Claim·차단 사유·이전 보강 보존 시험을 통과시킨다.

### Task 2: 실제 파이프라인 차단 증명

**Files:**
- Modify: `tests/unit/test_numeric_role_gate_pipeline.py`

1. 보호 역할 3종과 수준값 오인 상태에서 official service가 호출되지 않는 시험을 작성한다.
2. 안전한 대상 상태는 숫자 역할 안전판에서 차단 사유를 반환하지 않는지 확인한다.
3. 기존 target link·sign direction 파이프라인 회귀시험을 함께 실행한다.

### Task 3: 381건 실행과 기록

**Files:**
- Create: `deliverables/CLAFACT_AUTO_8번_1단계_숫자역할오인차단_20260825.csv`
- Create: `deliverables/CLAFACT_AUTO_8번_1단계_숫자역할오인차단_파이프라인보강_20260825.jsonl`
- Create: `deliverables/CLAFACT_AUTO_8번_1단계_숫자역할오인차단_실행이력_20260825.csv`
- Create: `deliverables/CLAFACT_AUTO_8번_1단계_숫자역할오인차단_검증이력_20260825.csv`
- Create: `deliverables/CLAFACT_AUTO_8번_1단계_숫자역할오인차단_결과보고_20260825.txt`
- Create: `deliverables/CLAFACT_AUTO_8번_체크리스트상태_1단계6완료_20260825.json`

1. 같은 381건을 통합 안전판으로 실행한다.
2. 안전 360건·차단 21건과 세부 사유 합계를 독립 대조한다.
3. 공식 서비스 호출 전 차단 시험을 실행한다.
4. 관련 회귀시험과 전체 단위시험을 실행한다.
5. 결과와 근거를 CSV·JSONL·이력·보고서·체크리스트에 기록한다.
6. 검증된 산출물만 커밋하고 현재 원격 브랜치에 푸시한다.
