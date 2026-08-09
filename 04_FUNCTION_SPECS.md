# CLAFACT-AUTO Function Specifications

## 핵심 함수

```python
parse_claim(sentence: str) -> ClaimSchema
split_complex_claim(sentence: str) -> list[str]
normalize_concept(claim: ClaimSchema) -> StandardConceptSchema
search_semantic_catalog(claim, concept, top_k=20) -> list[KosisCandidateSchema]
apply_hard_guard(claim, candidate) -> HardGuardResult
semantic_match(claim, candidates) -> list[MatchResult]
resolve_evidence_cell(claim, candidate) -> EvidenceCellSchema
fetch_kosis_value(cell) -> KosisValue
build_calculation_plan(claim, base_cell) -> CalculationPlan
calculate(plan, values) -> float
make_verdict(...) -> VerdictSchema
```

## parse_claim()

- 12 Slot 생성
- Structured Output 필수
- 누락/모호 시 HOLD/HUMAN_REVIEW

## split_complex_claim()

복수 수치 문장을 단일 Claim으로 분리.

## normalize_concept()

우선순위:
1. exact alias
2. normalized alias
3. similarity
4. LLM assist
5. unresolved

## search_semantic_catalog()

Standard Concept + Slot 조건으로 KOSIS 후보 탐색.

## apply_hard_guard()

Semantic Score 이전 실행.

대표 reject code:
- FREQUENCY_CONFLICT
- REGION_GRANULARITY_CONFLICT
- AGE_DIMENSION_REQUIRED
- SEX_DIMENSION_REQUIRED
- POPULATION_SCOPE_CONFLICT
- UNIT_CONFLICT
- FORECAST_CLAIM
- TIME_NOT_AVAILABLE

## semantic_match()

- hard guard 통과 후보만 점수화
- Top1/Top2 Margin 계산
- 임계값 미달은 HOLD

## resolve_evidence_cell()

핵심 좌표:
ORG_ID / TBL_ID / ITM_ID / OBJ_ID / MEMBER / PRD_SE / PRD_DE / UNIT

## fetch_kosis_value()

필수:
- timeout
- retry
- backoff
- response validation
- snapshot hash

## calculate()

분리 권장:
- compare_direct_value()
- calculate_difference()
- calculate_growth_rate()
- calculate_ratio()
- calculate_share()
- calculate_multiple()
- calculate_rank()
- check_threshold()

## make_verdict()

최종 판정은 규칙 기반.
LLM은 설명 문장 생성에만 제한적으로 사용.
