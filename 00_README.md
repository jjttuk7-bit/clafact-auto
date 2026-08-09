# CLAFACT-AUTO CODEX 구현 문서 패키지

## 목적

이 문서 묶음은 CLAFACT-AUTO를 CODEX로 구현하기 위한 공식 구현 기준이다.

CLAFACT-AUTO의 목표는 뉴스 기사 속 수치 Claim을 자동으로 구조화하고,
CLAFACT Semantic Standard와 KOSIS Semantic Catalog를 이용해
정확한 KOSIS Evidence Cell을 찾은 뒤,
공식값을 조회하고 결정론적 계산을 수행해
최종 Verdict를 생성하는 것이다.

핵심 흐름:

```text
NEWS ARTICLE
→ Claim 분리/선별
→ 12 Semantic Slots
→ Semantic Standard
→ KOSIS Semantic Catalog
→ Hard Guard
→ Semantic Matching
→ Match Candidate
→ Evidence Cell
→ KOSIS Official Value
→ Deterministic Calculation
→ Verdict
→ AUTO / HOLD / HUMAN_REVIEW
```

## 문서 구성

1. `AGENTS.md` — CODEX가 반드시 따라야 하는 프로젝트 규칙
2. `01_PRODUCT_REQUIREMENTS.md` — 기능/비기능 요구사항
3. `02_SYSTEM_ARCHITECTURE.md` — 전체 시스템 구조와 모듈 관계
4. `03_DATA_SCHEMAS.md` — Claim, Concept, Candidate, Evidence, Verdict 스키마
5. `04_FUNCTION_SPECS.md` — 핵심 함수 명세
6. `05_KOSIS_INTEGRATION.md` — KOSIS Metadata/Catalog/API 연동 기준
7. `06_TEST_AND_GOLDSET.md` — 단계별 골든셋 및 회귀 테스트 기준
8. `07_UI_SPEC.md` — Streamlit MVP 화면 요구사항
9. `08_IMPLEMENTATION_ROADMAP.md` — CODEX 구현 순서와 완료 조건
10. `09_CODEX_MASTER_PROMPT.md` — CODEX에 그대로 넣는 구현 프롬프트

## 현재 자산

- KOSIS 검증 대상 Claim 약 1,531건
- Claim 12 Semantic Slot 구조
- Semantic Standard Seed Concept 31개
- KOSIS 후보 통계표 Metadata 350개
- Hard Guard 설계
- Semantic Matching 실험
- Evidence Cell 개념
- 기존 CLAFACT 검증 운영 콘솔

## 설계 원칙

- KOSIS-only 범위로 먼저 완성한다.
- LLM은 의미 해석과 계획 수립에 사용한다.
- 공식값 조회와 계산은 코드/함수로 수행한다.
- 구조적 충돌은 Semantic Score로 보상하지 않는다.
- 자동 판정이 불확실하면 HOLD 또는 HUMAN_REVIEW로 보낸다.
- 모든 단계는 Structured Output을 사용한다.
- 최종 판정은 Evidence와 계산 로그를 남긴다.
