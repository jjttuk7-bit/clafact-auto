# AGENTS.md — CLAFACT-AUTO CODEX 구현 규칙

## 최우선 필수 참조

모든 구현·수정·테스트·리뷰 작업은 시작하기 전에 반드시 루트의 [CLAFACT_AUTO_EXECUTION_CONTRACT.md](CLAFACT_AUTO_EXECUTION_CONTRACT.md)를 먼저 읽고 준수한다.

- 이 계약은 CLAFACT-AUTO의 공식 API 직접 조회 원칙과 완료 조건을 정의한다.
- 하위 설계·계획·테스트 관행이 이 계약과 충돌하면 이 계약을 우선한다.
- 신규 Claim의 공식 조회 경로를 실제로 실행하지 않는 변경은 핵심 파이프라인 완성으로 인정하지 않는다.

## 프로젝트 목적

CLAFACT-AUTO는 뉴스 기사 속 수치 Claim을 KOSIS 공식 통계와 자동으로 검증하는 시스템이다.

반드시 다음 파이프라인을 구현한다.

```text
Article
→ Claim Extraction
→ Claim Split
→ 12 Slot Parsing
→ Semantic Standard Mapping
→ KOSIS Catalog Search
→ Hard Guard
→ Semantic Matching
→ Evidence Cell Resolution
→ KOSIS Value Fetch
→ Deterministic Calculation
→ Verdict
```

## 절대 원칙

1. KOSIS 공식값을 LLM이 생성하지 않는다.
2. 실제 계산은 Python 함수가 수행한다.
3. 모든 LLM 출력은 Structured Output으로 제한한다.
4. Hard Guard가 Semantic Score보다 먼저 실행된다.
5. 모호한 후보를 강제로 Top-1으로 고르지 않는다.
6. 불확실하면 HOLD/HUMAN_REVIEW로 라우팅한다.
7. 핵심 함수에는 테스트를 작성한다.
8. API key는 환경변수로 관리한다.
9. 기존 CLAFACT 운영 데이터는 직접 변경하지 않는다.
10. UI보다 Core Engine을 먼저 완성한다.

## 권장 프로젝트 구조

```text
clafact_auto/
├─ app/
│  └─ streamlit_app.py
├─ core/
│  ├─ claim_parser.py
│  ├─ claim_splitter.py
│  ├─ semantic_normalizer.py
│  ├─ catalog_search.py
│  ├─ hard_guard.py
│  ├─ semantic_matcher.py
│  ├─ evidence_resolver.py
│  ├─ kosis_fetcher.py
│  ├─ calculator.py
│  └─ verdict_engine.py
├─ schemas/
│  ├─ claim.py
│  ├─ concept.py
│  ├─ candidate.py
│  ├─ evidence.py
│  └─ verdict.py
├─ data/
│  ├─ semantic_standard/
│  └─ kosis_catalog/
├─ tests/
│  ├─ unit/
│  ├─ integration/
│  └─ goldset/
├─ config/
│  └─ settings.py
└─ logs/
```

## 개발 기준

- Python 3.12+
- Pydantic v2
- 타입힌트 필수
- 함수당 단일 책임
- 네트워크 접근은 adapter 계층으로 분리
- 로그에 API key 저장 금지
- 핵심 결과에는 버전 정보 기록

## 버전 필드

```text
dataset_version
preprocess_version
claim_schema_version
semantic_standard_version
kosis_catalog_version
matching_version
calculation_version
```
