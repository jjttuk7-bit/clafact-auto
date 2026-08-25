# Direct Value Indicator Unit Compatibility Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 직접값 381건 중 원문 대상값이 연결된 365건의 지표 의미와 단위 호환성을 평가하고 통합 파이프라인에 반영한다.

**Architecture:** `core/indicator_unit_compatibility.py`가 지표·단위·대상 역할을 의미 종류로 정규화해 판정한다. `tools/build_direct_value_indicator_unit_audit.py`가 381건 결과 CSV·파이프라인 보강 JSONL·검증 JSON을 만든다. 통합 파이프라인은 호환되지 않은 보강 Claim을 공식조회 전에 정확한 구조화 사유로 중단한다.

**Tech Stack:** Python 표준 라이브러리, Pydantic v2, pytest

---

### Task 1: 의미 종류와 호환 판정

1. 사람 수·금액·비율·물량·가구·면적의 정상 조합 시험을 작성한다.
2. 수출액-대, 총인구-원, 경제성장률-개의 충돌 시험을 작성한다.
3. 인원·금액 지표의 증감값 `%`가 정상 상대 증감으로 유지되는 시험을 작성한다.
4. 시험 실패를 확인한 뒤 최소 판정기를 구현하고 통과시킨다.

### Task 2: 파이프라인 보강과 사전 중단

1. 호환 결과가 기존 `slot_enrichment`를 보존하며 병합되는 시험을 작성한다.
2. 충돌·지표 보완·검토 상태에서 공식 서비스가 호출되지 않는 시험을 작성한다.
3. 정상 상태는 기존 원문 대상 연결 경로를 그대로 통과하는 시험을 작성한다.
4. 시험 실패를 확인한 뒤 최소 구현하고 통과시킨다.

### Task 3: 381건 실행과 기록

1. 대상값 원문 연결 CSV를 381건 호환 결과로 변환한다.
2. 365건 평가·16건 미평가와 상태별 건수를 독립 검증한다.
3. 성공·실패 원인, 적용 범위, 결과 보고서와 체크리스트를 저장한다.
4. 관련 회귀시험과 전체 단위시험을 실행한다.
5. 검증된 구현과 산출물을 로컬 커밋하고 원격 브랜치에 푸시한다.
