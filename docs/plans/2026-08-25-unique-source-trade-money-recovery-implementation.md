# 단일 원문 무역금액 복구 구현 계획

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 단일 직접값 무역 Claim에서 OpenAI의 금액 자릿수 오류를 원문 달러 표현으로 안전하게 복구한다.

**Architecture:** 기존 `trade_money_normalizer`에서 원문 달러 표현의 개수와 Claim 계산 방식을 먼저 검사한다. 유일한 원문 금액이면 기존 일치 정규화를 유지하고, 불일치하더라도 직접값 Claim에 한해 원문 금액으로 교정한다. 복수 금액과 계산형 Claim은 fail-closed로 유지한다.

**Tech Stack:** Python 3.12+, Pydantic v2, pytest

---

### Task 1: 안전 경계 회귀 테스트

**Files:**
- Modify: `tests/unit/test_trade_money_normalization.py`

1. `10.56 십억 달러`가 `-1,056,000,000 달러`로 복구되는 실패 테스트를 작성한다.
2. 원문에 달러 금액이 여러 개면 교정하지 않는 테스트를 작성한다.
3. 계산형 Claim이면 불일치 금액을 교정하지 않는 테스트를 작성한다.
4. 테스트를 실행해 새 단일 금액 사례만 실패하는지 확인한다.

### Task 2: 최소 공통 규칙 구현

**Files:**
- Modify: `core/trade_money_normalizer.py`

1. 원문 달러 금액을 한 번만 추출한다.
2. 정확히 하나가 아니면 기존 Claim을 반환한다.
3. 기존 금액이 원문과 같으면 현재 정규화 동작을 유지한다.
4. 금액이 다르면 `DIRECT_VALUE`에 한해서만 원문 금액을 사용한다.
5. 적자·흑자 부호 정규화를 동일하게 적용한다.

### Task 3: 통합·전체 검증

**Files:**
- Test: `tests/unit/test_trade_money_normalization.py`
- Test: `tests/integration/test_record_comparison_unified_pipeline.py`

1. 집중 테스트를 실행한다.
2. 전체 pytest를 실행한다.
3. 실제 OpenAI Structured Output과 공식 API를 사용하는 대시보드 동일 경로로 대표 문장을 실행한다.
4. 금액, 기간, 자동처리 상태, 공식 조회 도달 여부를 확인한다.
5. 관련 파일만 커밋하고 원격 기능 브랜치와 `main`에 푸시한다.
