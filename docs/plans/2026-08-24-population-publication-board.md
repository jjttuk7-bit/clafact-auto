# 인구동향 공식 공표자료 연결 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 인구동향조사의 월별 공식 보도자료를 올바른 국가데이터처 게시판에서 찾아 기사 당시 공표 여부를 검증한다.

**Architecture:** KOSIS 통계설명 API와 공식값 API 직접 조회는 그대로 유지한다. 통계명에서 공식 보도자료 검색 게시판으로 연결하는 프로필 중 인구동향조사의 게시판 번호만 실제 공식 게시판 `204`로 교정하며, 기간·제목·게시일 일치 검사는 기존 fail-closed 경로를 그대로 사용한다.

**Tech Stack:** Python 3.12, Pydantic v2, pytest, KOSIS Open API, 국가데이터처 공식 게시판

---

### Task 1: 실패 원인 고정

**Files:**
- Modify: `tests/unit/test_kosis_publication.py`

**Step 1: Write the failing test**

인구동향조사가 게시판 `204`와 검색어 `YYYY년 M월 인구동향`을 사용해야 한다는 테스트를 추가한다.

**Step 2: Run test to verify it fails**

Run: `python -m pytest -q tests/unit/test_kosis_publication.py -k population_release`

Expected: 게시판이 기존 `213`이므로 FAIL.

### Task 2: 공식 게시판 프로필 수정

**Files:**
- Modify: `core/kosis_publication.py`

**Step 1: Write minimal implementation**

`인구동향조사`의 공식 보도자료 게시판을 `204`로 변경한다. 검색 제목, 기간 일치, 게시일 파싱, 공식 도메인 제한은 변경하지 않는다.

**Step 2: Run focused tests**

Run: `python -m pytest -q tests/unit/test_kosis_publication.py tests/unit/test_official_value_fetcher.py`

Expected: PASS.

### Task 2B: 기사 이후 개정값 오판 차단

**Files:**
- Modify: `tests/unit/test_snapshot_asof.py`
- Modify: `tests/unit/test_official_value_fetcher.py`
- Modify: `core/snapshot_asof.py`
- Modify: `core/kosis_fetcher.py`

**Step 1: Write failing tests**

공식 보도자료 공표일은 기사 전이지만 KOSIS `LST_CHN_DE`가 기사 후인 값은 자동 판정하지 않는 테스트를 추가한다.

**Step 2: Implement the minimal guard**

공표일과 값 최종수정일이 모두 기사일 이하여야 현재 KOSIS 값을 기사시점 증거로 사용한다. 최종수정일은 결과 provenance에 보존한다.

**Step 3: Run focused tests**

Run: `python -m pytest -q tests/unit/test_snapshot_asof.py tests/unit/test_official_value_fetcher.py`

Expected: PASS.

### Task 3: 실제 공식 재실행

**Files:**
- Read: `artifacts/clafact_final_completion_202608/birth_reporting_month_20260824/input_registry.jsonl`
- Create: `artifacts/clafact_final_completion_202608/population_publication_20260824/run/claim_verification_results.jsonl`
- Create: `artifacts/clafact_final_completion_202608/population_publication_20260824/run/coverage_report.json`

**Step 1: Run bounded official pipeline**

출생아 월별 증가율 3건만 `tools/run_clafact_pipeline.py --stored-slots-only`로 실행한다.

**Step 2: Verify official evidence**

각 Claim에 KOSIS 값 출처 URL·응답 해시와 국가데이터처 보도자료 URL·공표일·내용 해시가 있는지 확인한다.

**Step 3: Verify calculation and verdict**

두 공식 월 값을 Python으로 계산한 결과와 뉴스의 증가율이 일치하는지 확인한다. 불일치하거나 기사 이후 공표이면 해당 이유로 보류한다.

### Task 4: 통합 원장과 회귀 검증

**Files:**
- Modify: `artifacts/clafact_final_completion_202608/CLAFACT_1542_통합진행원장.csv`
- Modify: `artifacts/clafact_final_completion_202608/CLAFACT_1542_통합진행원장_요약.json`

**Step 1: Rebuild consolidated ledger**

새 실행 결과를 기존 1,542건 통합 원장에 누적한다.

**Step 2: Run full regression**

Run: `python -m pytest -q --ignore=tests/unit/test_goal_completion_audit.py --ignore=tests/integration/test_final_baseline.py`

Expected: 모든 테스트 PASS.

**Step 3: Commit and push**

이번 코드·테스트·실행 증거·원장만 커밋하고 `codex/final-completion-execution`에 푸시한다.
