# Structural Pre-Split Detector Design

## Goal

Admission 전에 한 문장 안의 독립적인 수치 사실주장을 감지해 `MULTI_CLAIM_SPLIT_REQUIRED`로 라우팅한다. 이는 KOSIS 값 조회 이전 단계이며, 공식값·판정은 생성하거나 조회하지 않는다.

## Decision

규칙은 숫자 개수만 보지 않는다. 아래 두 조건이 동시에 있을 때만 분리 후보로 본다.

1. 숫자 묶음이 둘 이상 존재한다.
2. 묶음 사이에 독립 주장 신호가 있다: 별도 지표/대상/시점, 병렬 접속, 또는 현재값과 비교 기준이 각각 완결된 주장이다.

현재값과 전년동월 대비 증감값은 각각 별도 Claim으로 분리한다. 기준연도 표기(예: 2020년=100)만 같은 Claim의 보조 메타데이터로 유지한다.

## Data Flow

`ClaimSchema.source_sentence` → `detect_structural_multi_claim` → Admission hard guard → existing splitter → child Claim parser → re-admission.

파서가 HOLD/HUMAN_REVIEW이면 detector 결과가 있더라도 공식 KOSIS 조회를 수행하지 않는다. CONTEXT_REQUIRED 재파싱 후에만 eligible이 될 수 있다.

## Verification

- 16개 Gold P0 `MULTI → ELIGIBLE` 문장을 regression fixture로 둔다.
- 단일 지표 + 비교 기준 문장은 false positive 방지 fixture로 둔다.
- unit/integration test 후 250건 Gold Set 재평가한다.