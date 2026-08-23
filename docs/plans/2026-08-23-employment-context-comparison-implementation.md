# Employment Context Comparison Recovery Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 같은 기사 앞 문맥에서 비교 기준이 하나로 확정되는 증감액 Claim만 두 시점 공식값 차이 계산으로 재분류하고, 선택한 고용 Claim 2건을 실제 KOSIS로 검증한다.

**Architecture:** 문맥 비교 기준 판별은 작은 결정론적 함수로 분리한다. 재분류 CLI가 같은 기사에서 대상보다 앞선 문장만 전달하며, 기존 `recover_validated_claim`과 공식 조회·계산·판정 경로를 재사용한다.

**Tech Stack:** Python 3.12, Pydantic v2, pytest, KOSIS official APIs

---

### Task 1: 문맥 비교 기준 판별

**Files:**
- Create: `core/context_comparison_resolver.py`
- Create: `tests/unit/test_context_comparison_resolver.py`

1. `전년 동월 대비`만 존재하면 `YEAR_OVER_YEAR`를 반환하는 실패 테스트를 작성한다.
2. `전년 동월 대비`와 `전월 대비`가 섞이면 아무 기준도 반환하지 않는 실패 테스트를 작성한다.
3. 테스트를 실행해 기능 부재로 실패하는지 확인한다.
4. 비교 표현을 정규화하고 단일 기준만 반환하는 최소 코드를 작성한다.
5. 테스트를 다시 실행해 통과시킨다.

### Task 2: 재분류 도구에 같은 기사 앞 문맥 연결

**Files:**
- Modify: `core/validated_claim_recovery.py`
- Modify: `tools/reclassify_change_amount_group.py`
- Modify: `tests/unit/test_validated_claim_recovery.py`
- Modify: `tests/unit/test_reclassify_change_amount_group.py`

1. 비교 기준이 없으면 문맥 없이는 재분류되지 않는 테스트를 고정한다.
2. 명시적 문맥 기준이 있으면 `DIFFERENCE`와 공식 근거 피연산자로 재분류되는 실패 테스트를 작성한다.
3. CLI가 다른 기사 문맥과 뒤 문장을 사용하지 않는 실패 테스트를 작성한다.
4. `--context-registry`를 필수 입력으로 추가하고 같은 기사 앞 문장만 수집한다.
5. 문맥 기준과 사용 문장을 감사 CSV 및 `slot_enrichment`에 저장한다.
6. 대상 단위 테스트를 통과시킨다.

### Task 3: 선택한 2건 재분류 및 공식 실행

**Files:**
- Create: `artifacts/clafact_final_completion_202608/employment_context_change_amount_2_live_20260823/*`

1. 두 Claim ID만 지정하여 재분류 도구를 실행한다.
2. 출력 Registry가 정확히 2건이며 둘 다 `DIFFERENCE`인지 확인한다.
3. `run_clafact_pipeline_bounded.py`를 `--stored-slots-only --no-resume --max-workers 1`로 실행한다.
4. 두 시점 공식값과 공표정보가 실제 API 근거로 남았는지 확인한다.
5. 개선 전후 CSV, 공식 단계 결과 CSV, 완료 판정 CSV를 생성한다.

### Task 4: 회귀 검증과 저장

1. 신규·관련 단위 테스트를 실행한다.
2. 전체 회귀 테스트를 실행하되 기존 외부 Registry 부재 테스트 2개만 제외한다.
3. 실행 산출물의 Claim 수, 공식 근거, 계산 Trace와 판정을 점검한다.
4. 변경 파일만 커밋하고 `codex/final-completion-execution`으로 푸시한다.
