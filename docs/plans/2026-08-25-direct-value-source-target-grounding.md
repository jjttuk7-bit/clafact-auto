# Direct Value Source Target Grounding Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 직접값 381건의 숫자 역할 결과를 감사 가능한 원문 대상 연결과 통합 파이프라인 보강 입력으로 만든다.

**Architecture:** `core/source_target_grounding.py`가 역할 결과를 원문 위치와 재검증하고 Registry 보강값을 만든다. `tools/build_direct_value_target_grounding.py`가 381건 CSV·JSONL·검증 JSON을 생성한다. 통합 파이프라인은 검증된 보강 표현을 원문 값 검증 범위로 소비하고, 미연결 상태는 공식조회 전에 명시적으로 중단한다.

**Tech Stack:** Python 표준 라이브러리, Pydantic v2, pytest

---

### Task 1: 원문 대상 연결 계약

1. 정상 연결, 보호 역할 차단, 값 없음, 중복값의 실패 시험을 작성한다.
2. 모듈 부재로 실패하는지 확인한다.
3. 정확한 표현·위치·상태·사유를 반환하는 최소 구현을 작성한다.
4. 시험 통과를 확인한다.

### Task 2: Registry 보강과 통합 파이프라인 소비

1. 연결 표현이 `slot_enrichment`에 병합되는 시험을 작성한다.
2. 통합 파이프라인이 전체 문장 대신 연결 표현으로 원문값을 검증하는 시험을 작성한다.
3. 미연결 보강 Claim이 공식 서비스 호출 전 정확한 사유로 중단되는 시험을 작성한다.
4. 시험 실패를 확인한 뒤 최소 구현하고 통과시킨다.

### Task 3: 381건 결과 생성과 기록

1. 역할 분류 CSV 381건을 결과 CSV·보강 JSONL·검증 JSON으로 변환한다.
2. 381건·365 연결·16 미연결, 원문 위치 불일치 0, 사유 누락 0을 독립 검증한다.
3. 실행 이력·쉬운 결과 보고서·체크리스트 상태를 저장한다.
4. 관련 회귀시험과 전체 단위시험을 실행하고 결과를 기록한다.
5. 검증된 변경과 산출물을 로컬 브랜치에 커밋한다.

