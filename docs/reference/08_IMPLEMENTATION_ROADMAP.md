# CLAFACT-AUTO CODEX Implementation Roadmap

## PHASE 0 — 프로젝트 뼈대
- 디렉터리
- pyproject.toml
- pytest
- logging
- .env.example

## PHASE 1 — Schema
- ClaimSchema
- StandardConceptSchema
- KosisCandidateSchema
- HardGuardResult
- MatchResult
- EvidenceCellSchema
- CalculationPlan
- VerdictSchema

## PHASE 2 — 데이터 로더
- 31 Seed Concept loader
- Alias loader
- 350 Metadata loader
- Catalog normalizer

## PHASE 3 — Claim Parser
- parse_claim()
- Structured Output
- parse_status

## PHASE 4 — Semantic Standard
- normalize_concept()
- alias exact match
- similarity fallback
- unresolved routing

## PHASE 5 — Catalog Search + Hard Guard
- search_semantic_catalog()
- apply_hard_guard()

## PHASE 6 — Semantic Matching
- weighted score
- Top1/Top2 Margin
- MATCH/HOLD routing

## PHASE 7 — Evidence Resolver
- item
- dimension/member
- time
- unit
- canonical key

## PHASE 8 — KOSIS Fetcher
- API client
- retry/backoff
- timeout
- response validation
- snapshot

## PHASE 9 — Calculation Engine
1. DIRECT_VALUE
2. DIFFERENCE
3. GROWTH_RATE
4. RATIO
5. SHARE
6. MULTIPLE
7. THRESHOLD
8. RANK

## PHASE 10 — Verdict Engine
- tolerance
- MATCH
- MISMATCH
- UNDETERMINED
- reason_code

## PHASE 11 — E2E Goldset
20~30건 자동 실행.

## PHASE 12 — Streamlit UI
Core Engine 완료 후 구현.

## PHASE 13 — 기존 CLAFACT 연동
HOLD/HUMAN_REVIEW adapter 추가.

## MVP 완료 정의

```text
뉴스 Claim
→ 12 Slot
→ Concept
→ KOSIS Table
→ Evidence Cell
→ Official Value
→ Calculation
→ Verdict
```

한 건을 자동으로 끝까지 통과시키면 1차 MVP 성립.
