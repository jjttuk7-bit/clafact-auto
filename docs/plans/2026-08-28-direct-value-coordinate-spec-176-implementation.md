# Direct Value Coordinate Spec 176 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 미해결 직접값 176건을 KOSIS 검색 명세로 전수 변환하고 기존 통합 공식 엔진으로 실행해 단계별 평가 원장을 만든다.

**Architecture:** 최신 230행 원장에서 정확한 176건을 고정한 뒤 Pydantic 검색 명세와 Claim Registry를 생성한다. 준비 완료 Claim만 기존 `unified_claim_pipeline`과 v3 공식 엔진에 투입하고, 준비 전 중단과 공식 실행 결과를 하나의 176행 평가 자료로 합친다.

**Tech Stack:** Python 3.12+, Pydantic v2, pytest, KOSIS 공식 API adapter, CSV/JSONL audit artifacts

---

### Task 1: 176건 범위 계약

**Files:**
- Create: `core/direct_value_coordinate_spec_scope.py`
- Test: `tests/unit/test_direct_value_coordinate_spec_scope.py`

1. 230행에서 공식완료·검증제외·유형이동·복수기간 이동을 제외하면 정확히 176건이어야 한다는 실패 테스트를 작성한다.
2. 테스트를 실행해 모듈 부재로 실패하는지 확인한다.
3. Claim ID·원문 해시·기존 사유·검증집합을 보존하는 scope와 manifest를 구현한다.
4. 테스트를 실행해 176건·고유 ID·해시가 통과하는지 확인한다.

### Task 2: KOSIS 검색 명세 스키마

**Files:**
- Create: `schemas/kosis_query_spec.py`
- Create: `core/kosis_query_spec_compiler.py`
- Test: `tests/unit/test_kosis_query_spec_compiler.py`

1. 직접값, 누계 무역, 국가 성장률, 품목 수출량, 시점 누락 사례의 기대 명세 테스트를 먼저 작성한다.
2. 테스트가 스키마·컴파일러 부재로 실패하는지 확인한다.
3. 측정값 종류, 단위·배율, 기간, 지역, 차원, 검색어, 공식 경로, 준비상태를 원문 기반으로 생성한다.
4. 기사에 없는 값을 만들지 않고 부족한 슬롯을 `PRE_VERIFICATION`으로 기록한다.
5. 단위 테스트를 통과시킨다.

### Task 3: 176건 Registry 재구성

**Files:**
- Create: `core/direct_value_coordinate_spec_registry.py`
- Test: `tests/unit/test_direct_value_coordinate_spec_registry.py`

1. 원장 한 행이 정확한 `ClaimRegistryRecord`로 변환되는 테스트를 작성한다.
2. 원문·기사일·값·단위·시점·지역·차원·계산방식의 손실 없는 변환을 구현한다.
3. 검색 명세 준비 완료 건만 공식 실행 Registry에 포함하는 테스트를 통과시킨다.

### Task 4: 전수 범위 생성 도구

**Files:**
- Create: `tools/build_direct_value_coordinate_spec_176.py`
- Test: `tests/unit/test_build_direct_value_coordinate_spec_176.py`

1. 임시 230행 fixture에서 manifest·176 명세·준비 Registry 생성 테스트를 작성한다.
2. 입력·코드·데이터 해시와 분류 합계를 기록하도록 구현한다.
3. 실제 최신 원장으로 176건 산출물을 생성하고 합계를 확인한다.

### Task 5: 기존 통합 공식 엔진 전량 실행

**Files:**
- Reuse: `tools/run_clafact_pipeline.py`
- Reuse: `core/unified_claim_pipeline.py`
- Output: `artifacts/direct_value_coordinate_spec_176_20260828/live_run/`

1. 준비 Registry 전 건을 한 프로세스에서 실행한다.
2. KOSIS Catalog·Metadata·Value·Publication API 호출 수를 coverage report에 보존한다.
3. 모든 입력이 terminal 상태를 갖고 실행 누락이 없는지 확인한다.

### Task 6: 176행 평가 원장과 단계별 지표

**Files:**
- Create: `core/direct_value_coordinate_spec_evaluation.py`
- Create: `tools/compile_direct_value_coordinate_spec_176.py`
- Test: `tests/unit/test_direct_value_coordinate_spec_evaluation.py`

1. 준비 전 중단과 공식 실행 결과가 정확히 176행으로 합쳐지는 테스트를 작성한다.
2. 단계별 상태·사유·후보 수·좌표 수·공식 출처·공표 상태·판정을 병합한다.
3. 전체와 세 검증집합별 분모·성공률이 일치하도록 구현한다.
4. 공식완료는 Evidence와 API Provenance가 정확히 1대1이고 공표가 검증된 경우만 인정한다.

### Task 7: 실제 산출물과 검증

**Files:**
- Create: `deliverables/CLAFACT_AUTO_8번_직접값_미해결176건_KOSIS검색명세_평가원장_20260828.csv`
- Create: `deliverables/CLAFACT_AUTO_8번_직접값_미해결176건_단계별평가보고서_20260828.txt`
- Create: `artifacts/direct_value_coordinate_spec_176_20260828/final_summary.json`

1. 176행 고유 ID·단계 합계·비율 분모를 검증한다.
2. 실제 API 요청 근거, URL, 해시, 조회시각의 누락을 검사한다.
3. 관련 테스트와 전체 회귀 테스트를 실행한다.
4. 비밀키가 산출물에 포함되지 않았는지 검사한다.
5. 변경사항과 실제 수치를 검토한 뒤 커밋하고 원격 main에 푸시한다.
