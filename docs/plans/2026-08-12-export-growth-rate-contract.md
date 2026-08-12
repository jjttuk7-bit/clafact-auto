# Export Growth Rate Contract Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 수출액 성장률 12슬롯 계약과 분기 비교기간 계산을 구현해 잘못된 Claim은 구체적 HOLD로, 완전한 Claim은 동적 Evidence 계산으로 보낸다.

**Architecture:** claim_slot_quality에서 구조적 결손을 선제 차단한다. dynamic_kosis_verifier는 명시된 comparison.type에 따라 월·분기·연간 비교 Evidence Cell을 결정하며 계산은 기존 Python calculator만 사용한다.

**Tech Stack:** Python 3.12, Pydantic v2, pytest

---

### Task 1: 성장률 슬롯 계약

**Files:**
- Modify: `tests/unit/test_claim_slot_quality.py`
- Modify: `core/claim_slot_quality.py`

1. 단위, comparison.type, direction, 다중 target, 품목 보존 실패 테스트를 작성한다.
2. 테스트를 실행해 RED를 확인한다.
3. 최소 계약 검사 함수를 구현한다.
4. focused test를 실행해 GREEN을 확인한다.

### Task 2: OpenAI Structured Output 지침

**Files:**
- Modify: `tests/unit/test_openai_function_claim_extractor.py`
- Modify: `core/openai_function_claim_extractor.py`

1. GROWTH_RATE 필수 슬롯 문구 테스트를 작성한다.
2. RED를 확인한다.
3. 1,600자 제한 안에서 프롬프트를 보완한다.
4. GREEN을 확인한다.

### Task 3: 분기 비교 Evidence Cell

**Files:**
- Modify: `tests/unit/test_cpi_dynamic_evidence.py`
- Modify: `core/dynamic_kosis_verifier.py`

1. 분기 전년 대비와 전분기 대비 기간 테스트를 작성한다.
2. RED를 확인한다.
3. YYYY-Qn 비교기간 계산을 구현한다.
4. GREEN을 확인한다.

### Task 4: 배치 검증

1. GROWTH_RATE 8건 Registry를 고정한다.
2. 8건 배치에서 CLAIM_PARSE_UNCERTAIN 8건을 확인한다.
3. 62건 배치에서 NO_HARD 잔여가 DIFFERENCE 1건인지 확인한다.
4. 전체 unit, integration, goldset 및 git diff --check를 실행한다.