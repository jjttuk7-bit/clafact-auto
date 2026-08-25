# Direct Value Numeric Role Classification Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 381개 직접값 Claim의 1,456개 원문 수치에 역할 또는 자동 대상 제외 이유를 결정론적으로 기록한다.

**Architecture:** `core/source_numeric_role_classifier.py`가 한 Claim의 저장 슬롯과 원문 수치 목록을 받아 역할을 반환한다. `tools/build_direct_value_numeric_roles.py`가 381행 CSV를 처리하고 결과 CSV·JSONL·검증 JSON을 생성한다.

**Tech Stack:** Python 표준 라이브러리, pytest

---

### Task 1: 역할 분류기

1. 연령·기간·순위·환산·대상값·증감값·모델 제외 시험을 작성한다.
2. 시험이 모듈 부재로 실패하는지 확인한다.
3. 우선순위 기반 최소 분류기를 구현한다.
4. 시험 통과를 확인한다.

### Task 2: 381건 실행 도구

1. 모든 수치에 역할/이유가 있어야 하는 실패 차단 시험을 작성한다.
2. 시험 실패를 확인한 뒤 CSV·JSONL·검증 JSON 생성을 구현한다.
3. 시험 통과를 확인한다.

### Task 3: 실제 실행과 기록

1. 1단계 수치 목록 CSV 381건에 실행한다.
2. Claim 381, 수치 1,456, 역할 누락 0, 제외 이유 누락 0을 검증한다.
3. 역할별 건수와 대상 충돌 건수를 결과·요약·체크리스트에 기록한다.
4. 시험과 실제 결과를 재검증하고 커밋한다.

