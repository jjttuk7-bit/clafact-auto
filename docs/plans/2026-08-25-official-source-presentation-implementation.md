# 공식 근거 출처 표시 구현 계획

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** KOSIS 값과 공식 작성기관 문서값을 대시보드·설명·검토 데이터에서 정확히 구분한다.

**Architecture:** 공식값 출처 판별을 Core의 단일 프레젠테이션 함수로 만들고 Streamlit과 설명기가 함께 사용한다. 근거 개수와 실행 추적은 기존 스키마를 변경하지 않고 공식 문서 provenance와 작성기관 단계를 포함하도록 확장한다.

**Tech Stack:** Python 3.12+, Pydantic v2, Streamlit, pytest

---

### Task 1: 출처 판별 계약

**Files:**
- Create: `core/official_source_presentation.py`
- Create: `tests/unit/test_official_source_presentation.py`

1. KOSIS 좌표가 있는 판정은 `KOSIS 공식값`을 반환하는 실패 테스트를 작성한다.
2. 좌표 없이 `OFFICIAL_DOCUMENT`만 있는 판정은 `공식 작성기관 문서값`을 반환하는 실패 테스트를 작성한다.
3. 테스트가 함수 부재로 실패하는지 확인한다.
4. 출처 판별 함수와 문서 provenance 행 생성 함수를 최소 구현한다.
5. 집중 테스트를 통과시킨다.

### Task 2: 근거 개수와 실행 추적

**Files:**
- Modify: `core/review_handoff.py`
- Modify: `core/trace_presentation.py`
- Modify: `tests/unit/test_review_handoff.py`
- Modify: `tests/unit/test_trace_presentation.py`

1. 공식 문서 provenance만 있는 판정의 근거 개수가 1인 실패 테스트를 작성한다.
2. 작성기관 검색·문서 조회 단계가 `어떤 데이터`에 들어가는 실패 테스트를 작성한다.
3. 실패 원인을 확인한다.
4. 근거 개수를 좌표 수와 provenance 수 중 큰 값으로 계산한다.
5. 두 작성기관 단계를 데이터 분기에 추가하고 집중 테스트를 통과시킨다.

### Task 3: 대시보드와 설명 연결

**Files:**
- Modify: `app/streamlit_app.py`
- Modify: `core/verdict_explainer.py`
- Modify: `tests/unit/test_verdict_explainer.py`
- Modify: `tests/test_streamlit_app.py`

1. 공식 문서 판정 설명이 `공식 작성기관 문서값`을 사용하는 실패 테스트를 작성한다.
2. Streamlit의 고정 `KOSIS 공식값` 표시가 출처 판별 결과를 사용하는 검사를 추가한다.
3. 출처 판별 함수를 성공 메시지·지표 제목·근거 제목에 연결한다.
4. 공식 문서 URL·조회시각·응답 해시를 표로 표시한다.
5. 집중 테스트를 통과시킨다.

### Task 4: 전체·라이브 검증과 배포

**Files:**
- Test: `tests/unit/test_official_source_presentation.py`
- Test: `tests/unit/test_review_handoff.py`
- Test: `tests/unit/test_trace_presentation.py`
- Test: `tests/unit/test_verdict_explainer.py`
- Test: `tests/test_streamlit_app.py`

1. 전체 pytest를 실행한다.
2. 대표 무역수지 Claim을 OpenAI Structured Output과 공식 조회 경로로 실행한다.
3. 최종 출처명이 `공식 작성기관 문서값`, 근거 개수가 1, 작성기관 단계가 `어떤 데이터`에 포함되는지 확인한다.
4. 관련 파일만 커밋한다.
5. 기능 브랜치와 `main`에 푸시해 Render 배포를 시작한다.
