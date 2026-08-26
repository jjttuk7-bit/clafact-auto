# Direct Value Coordinate and Publication Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 좌표 실패 92건과 공표 실패 18건을 공식 구조정보 기반 공통 규칙으로 줄이고, 미사용 Claim·신규 뉴스에서 실제 공식 판정 완료 증가를 증명한다.

**Architecture:** 현재 `OfficialEvidenceService`의 실행 순서는 유지한다. 별도 분석/실행 도구가 원장 집합과 감사정보를 고정하고, Core에는 공식 메타데이터로 증명 가능한 최소 규칙만 테스트 우선으로 추가한다. 최종 결과는 기존 230행 원장과 엄격한 공식완료 조건으로 합친다.

**Tech Stack:** Python 3.11+, Pydantic v2, pytest, pandas, KOSIS 공식 Catalog/Metadata/Parameter/통계설명 API

---

### Task 1: 대상·기준선 고정

**Files:**
- Create: `core/direct_value_coordinate_publication_scope.py`
- Create: `tools/build_direct_value_coordinate_publication_scope.py`
- Test: `tests/unit/test_direct_value_coordinate_publication_scope.py`

1. 발견용·중간검증용·최종미사용 집합에서 좌표/공표 대상만 뽑고 ID·원문 SHA-256을 고정하는 실패 테스트를 작성한다.
2. 테스트가 선택 수와 해시 불일치 때문에 실패하는지 확인한다.
3. 좌표 사유 2종과 공표 사유 2종만 선택하고 최종미사용 원문을 분석 출력에서 숨기는 최소 구현을 작성한다.
4. 테스트를 통과시키고 범위 manifest를 생성한다.

### Task 2: 발견용 좌표 실패의 실제 경계 진단

**Files:**
- Create: `core/official_coordinate_diagnostics.py`
- Create: `tools/diagnose_direct_value_coordinates.py`
- Test: `tests/unit/test_official_coordinate_diagnostics.py`

1. Catalog/Metadata 요청 성공 여부, Hard Guard 탈락 이유, 좌표 축별 미확정 이유를 보존하는 실패 테스트를 작성한다.
2. 기존 실행 결과를 읽어 공식 조회 미시도와 조회 후 좌표 미확정을 구분하지 못하는 실패를 확인한다.
3. 공식 응답에 근거한 진단 레코드와 비-KOSIS 관측값 제외 판정을 구현한다.
4. 발견용 대상만 진단하고 공통 원인별 건수와 대표 공식 구조를 기록한다.

### Task 3: 좌표 공통 규칙 구현

**Files:**
- Modify: `core/claim_dimensions.py`
- Modify: `core/evidence_resolver_impl.py`
- Modify: `core/structural_candidate_selector.py`
- Modify: `core/official_evidence_service.py`
- Test: `tests/unit/test_claim_dimensions.py`
- Test: `tests/unit/test_evidence_resolver.py`
- Test: `tests/unit/test_structural_candidate_selector.py`
- Test: `tests/unit/test_official_evidence_service.py`

1. 발견용 진단에서 반복 확인된 하나의 원인마다 신규 뉴스 형태의 실패 테스트를 먼저 작성한다.
2. 테스트가 기존 코드에서 정확한 좌표 실패로 재현되는지 확인한다.
3. Claim ID·원문·표 ID 없이 공식 메타데이터의 고유 일치만 사용하는 최소 규칙을 구현한다.
4. 각 규칙별 단위 테스트와 기존 공식 엔진 테스트를 통과시킨다.

### Task 4: 발견용과 중간검증용 좌표 재실행

**Files:**
- Create: `tools/run_direct_value_coordinate_publication_group.py`
- Test: `tests/unit/test_run_direct_value_coordinate_publication_group.py`

1. 집합 순서 강제, 최대 실행 수, 체크포인트 서명, 공식 근거 감사 열을 검증하는 실패 테스트를 작성한다.
2. 최종미사용 집합의 조기 실행과 과거 체크포인트 재사용이 차단되는지 확인한다.
3. 발견용 영향 대상만 실제 API로 실행하고 개선 전후를 기록한다.
4. 코드 수정 없이 중간검증용 영향 대상을 실행해 일반화 성과를 기록한다.

### Task 5: 공표 확인 공통 경로 보강

**Files:**
- Modify: `core/kosis_publication.py`
- Modify: `core/official_publication_claim_verifier.py`
- Modify: `core/official_evidence_service.py`
- Test: `tests/unit/test_kosis_publication.py`
- Test: `tests/unit/test_official_publication_claim_verifier.py`
- Test: `tests/unit/test_official_evidence_service.py`

1. 대상 기간과 공표문서 기간이 다르거나 URL/해시가 없는 경우를 거부하는 실패 테스트를 작성한다.
2. 발견용 공표 실패에서 실제 공식 경로의 실패 위치를 재현한다.
3. KOSIS 통계설명→대상 기간별 KOSIS/작성기관 발표자료의 순서로 조회하고 증거를 보존하는 최소 구현을 작성한다.
4. 발견용을 실행한 뒤 코드 수정 없이 중간검증용으로 확인한다.

### Task 6: 최종미사용·신규 뉴스 수용 시험

**Files:**
- Create: `tools/run_direct_value_coordinate_publication_acceptance.py`
- Test: `tests/unit/test_direct_value_coordinate_publication_acceptance.py`

1. 최종미사용 집합이 이전 실행 기록에 없을 때만 실행되도록 실패 테스트를 작성한다.
2. 최종미사용 좌표/공표 대상은 마지막에 한 번만 실제 공식 API로 실행한다.
3. 발견용 원문과 다른 신규 뉴스 문장으로 Streamlit 동일 Core 경로를 실행한다.
4. 좌표·값·공표 URL·해시·판정이 모두 있는 엄격 완료만 성공으로 집계한다.

### Task 7: 원장 통합·검증·배포

**Files:**
- Create: `core/direct_value_coordinate_publication_results.py`
- Create: `tools/compile_direct_value_coordinate_publication_results.py`
- Test: `tests/unit/test_direct_value_coordinate_publication_results.py`
- Modify: `deliverables/CLAFACT_AUTO_8번_직접값_230건_일반화최종원장_20260827.csv`

1. 230행·230 고유 ID, 엄격 공식완료, 증거-출처 1:1, 집합 순서, 실행 서명을 검증하는 실패 테스트를 작성한다.
2. 모든 실제 실행을 같은 230행 CSV에 누적하고 요약/보고서를 생성한다.
3. 전체 테스트와 실제 API 수용 시험을 다시 실행한다.
4. 독립 코드 리뷰 후 Critical/Important를 수정한다.
5. 커밋·원격 main 푸시·Render 응답 확인을 수행한다.

