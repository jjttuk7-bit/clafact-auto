# Claim Reporting Precision Tolerance Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 기사에 표시된 퍼센트 Claim의 소수 자릿수로 Verdict 허용오차를 계산한다.

**Architecture:** `dynamic_kosis_verifier._claim_tolerance`가 원문의 퍼센트 숫자를 Claim 값과 대응시켜 반올림 단위를 계산한다. 기존 Verdict 엔진과 Evidence 계산은 변경하지 않는다.

**Tech Stack:** Python 3.12+, pytest, Pydantic v2

---

### Task 1: 표시 정밀도 회귀 테스트

**Files:**
- Create: `tests/unit/test_claim_tolerance.py`
- Modify: `core/dynamic_kosis_verifier.py`

1. `0.2%`가 ±0.05%p, `1.23%`가 ±0.005%p임을 요구하는 테스트를 작성한다.
2. 테스트를 실행해 기존 고정 ±0.01 때문에 실패함을 확인한다.
3. 원문의 `%` 숫자를 Claim 값과 대응시키는 최소 helper를 구현한다.
4. 관련 테스트와 취업자 동적 E2E를 실행한다.
5. 동일 Claim에 `make_verdict`를 적용해 MATCH를 확인한다.
6. 변경을 커밋하고 main에 푸시한다.