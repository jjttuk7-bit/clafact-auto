# Contextual Semantic Mapping Implementation Plan

> **For Codex:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan task-by-task.

**Goal:** dimension 문맥을 포함한 Semantic Mapping과 CPI 상세 운영 표준을 연결해 배추 물가 Claim을 동적 KOSIS AUTO 판정까지 통과시킨다.

**Architecture:** Claim 슬롯은 불변으로 유지하고 Semantic Mapper 내부에서 복합 라벨 후보를 생성한다. 공식 별칭과 KOSIS 검색어는 `concept_seed_v1.json`에 저장하며, 공유 verifier가 MATCHED/UNRESOLVED 상태에 맞는 trace를 기록한다.

**Tech Stack:** Python 3.12, Pydantic v2, pytest, Streamlit, KOSIS Open API

---

### Task 1: Contextual Semantic Labels

**Files:**
- Modify: `core/semantic_normalizer.py`
- Test: `tests/unit/test_semantic_normalizer.py`

1. `indicator=물가`, `dimension.product=배추`가 `배추 물가` alias에 매핑된다는 실패 테스트를 작성한다.
2. 테스트가 `UNRESOLVED`로 실패하는지 실행한다.
3. dimension member + indicator 복합 라벨을 구체성 순으로 생성해 기존 deterministic matching에 공급한다.
4. 단일 매치와 다중 매치 안전성 테스트를 통과시킨다.

### Task 2: Operational CPI Detail Standard

**Files:**
- Modify: `data/semantic_standard/concept_seed_v1.json`
- Test: `tests/unit/test_data_loader.py`

1. `CPI_DETAIL:A02A01701`과 공식 검색어 두 개가 Registry에서 로드돼야 한다는 실패 테스트를 작성한다.
2. 테스트가 Concept 부재로 실패하는지 실행한다.
3. CPI 상세 Concept를 버전형 운영 데이터에 추가한다.
4. 데이터 로더·중복 ID·standard_key 검증을 실행한다.

### Task 3: Accurate Semantic Trace

**Files:**
- Modify: `core/dynamic_kosis_verifier.py`
- Modify: `core/claim_verification_service.py`
- Modify: `app/streamlit_app.py`
- Test: `tests/unit/test_dynamic_kosis_verifier.py`
- Test: `tests/test_streamlit_app.py`

1. UNRESOLVED Concept가 `SEMANTIC_MAPPING` PASS로 기록되지 않아야 한다는 실패 테스트를 작성한다.
2. 공유 verifier가 `CONCEPT_NOT_FOUND` HOLD를 반환하도록 최소 구현한다.
3. Streamlit 단일·배치 경로도 Catalog 호출 전에 동일 HOLD 계약을 사용하게 한다.
4. 기존 MATCHED 경로 trace가 유지되는지 검증한다.

### Task 4: Dynamic CPI E2E

**Files:**
- Test: `tests/integration/test_contextual_cpi_dynamic_e2e.py`
- Modify only if required by test evidence: catalog/evidence adapters

1. 실제 Claim 구조, Semantic Registry, 공식 CPI metadata fixture, 공식 value snapshot을 사용하는 E2E 실패 테스트를 작성한다.
2. Concept → Catalog → Guard → Evidence → Value → Calculation → Verdict 각 단계를 검증한다.
3. `DT_1J22112`, `A02A01701`, 202510·202410, 약 `-34.4968`, MATCH/AUTO를 단언한다.
4. 특정 문장/Claim ID production 분기가 없는지 검색한다.

### Task 5: Verification and Delivery

1. 집중 테스트를 실행한다.
2. 동일 문장 Streamlit E2E를 실행한다.
3. 전체 pytest를 실행한다.
4. 변경 파일만 커밋하고 `main`에 푸시한다.
5. 완성된 범위와 다음 병목을 보고한다.

