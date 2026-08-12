# Export Difference Contract Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 수출액 DIFFERENCE 12슬롯 계약과 동적 KOSIS 두 시점 Python 차이 판정을 구현한다.

**Architecture:** claim_slot_quality가 명시적 피연산자·단위·방향을 검증한다. dynamic_kosis_verifier는 성장률과 동일한 비교기간 해석을 재사용해 두 Evidence Cell을 만들고 calculator의 DIFFERENCE를 호출한다.

**Tech Stack:** Python 3.12, Pydantic v2, pytest

---

### Task 1: 슬롯 계약

**Files:**
- Modify: `tests/unit/test_claim_slot_quality.py`
- Modify: `core/claim_slot_quality.py`

1. 누락·단위·산술·방향 실패 테스트와 완전한 계약 PASS 테스트를 작성한다.
2. RED를 확인한다.
3. 최소 계약 검사를 구현한다.
4. GREEN을 확인한다.

### Task 2: 동적 Difference Evidence와 Verdict

**Files:**
- Modify: `tests/unit/test_cpi_dynamic_evidence.py`
- Modify: `core/dynamic_kosis_verifier.py`
- Modify: `core/evidence_resolver.py`
- Modify: `core/hard_guard.py`

1. 두 공식 기간 조회와 감소폭 MATCH 테스트를 작성한다.
2. RED를 확인한다.
3. DIFFERENCE 비교 셀·단위·방향 판정을 최소 구현한다.
4. GREEN을 확인한다.

### Task 3: OpenAI 계약 및 배치

**Files:**
- Modify: `tests/unit/test_openai_function_claim_extractor.py`
- Modify: `core/openai_function_claim_extractor.py`

1. 명시적 피연산자 프롬프트 테스트를 RED→GREEN으로 구현한다.
2. A00904_8과 수출액 62건을 재실행한다.
3. NO_HARD 0건과 세부 HOLD 사유를 확인한다.
4. 전체 unit, integration, goldset, git diff --check를 실행한다.