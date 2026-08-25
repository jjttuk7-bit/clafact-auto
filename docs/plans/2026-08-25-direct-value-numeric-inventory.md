# Direct Value Numeric Inventory Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 동결된 직접값 Claim 381건의 모든 원문 숫자 표현을 위치·문맥과 함께 결정론적으로 목록화한다.

**Architecture:** `core/source_numeric_inventory.py`가 한 문장의 수치 표현과 위치를 반환한다. `tools/build_direct_value_numeric_inventory.py`가 동결 CSV를 읽어 Claim별 목록 CSV·JSONL·검증 JSON을 만들고 입력 계수와 숫자 문자 포함률을 검사한다.

**Tech Stack:** Python 3.12+, 표준 라이브러리 `re`, `csv`, `json`, `hashlib`, pytest

---

### Task 1: 수치 표현 추출기

**Files:**
- Create: `core/source_numeric_inventory.py`
- Test: `tests/unit/test_source_numeric_inventory.py`

1. 날짜·통계값·범위·연령·단위 없는 숫자·한글 수량의 기대 범위를 시험으로 작성한다.
2. `python -m pytest -q tests/unit/test_source_numeric_inventory.py`를 실행해 모듈 부재 실패를 확인한다.
3. 겹치는 후보 중 가장 긴 범위를 선택하고 원문 순서를 보존하는 최소 구현을 작성한다.
4. 같은 시험을 실행해 통과를 확인한다.

### Task 2: 381건 목록 생성과 실패 차단

**Files:**
- Create: `tools/build_direct_value_numeric_inventory.py`
- Test: `tests/unit/test_build_direct_value_numeric_inventory.py`

1. Claim별 1행, 수치 목록 JSON, 원문 숫자 미포함 위치 0을 요구하는 시험을 작성한다.
2. 시험을 실행해 기능 부재 실패를 확인한다.
3. CSV·JSONL·검증 JSON 생성과 381건 계수 검증을 구현한다.
4. 시험을 실행해 통과를 확인한다.

### Task 3: 실제 381건 실행과 증거 기록

**Files:**
- Create: `artifacts/direct_value_381_numeric_inventory_20260825/*`
- Create: `deliverables/CLAFACT_AUTO_8번_1단계_원문수치목록화_20260825.csv`
- Create: `deliverables/CLAFACT_AUTO_8번_1단계_원문수치목록화_요약_20260825.txt`
- Create: `deliverables/CLAFACT_AUTO_8번_체크리스트상태_1단계1완료_20260825.json`

1. 동결 CSV 381건을 대상으로 도구를 실행한다.
2. 입력·결과·고유 Claim번호 381, 미포함 숫자 위치 0, 위치 불일치 0을 확인한다.
3. 결과 해시와 분포를 CSV·TXT·체크리스트 상태에 기록한다.
4. 관련 시험과 실제 결과 검증을 다시 실행한다.
5. 변경 파일만 커밋한다.

