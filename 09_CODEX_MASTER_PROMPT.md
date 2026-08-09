# CLAFACT-AUTO CODEX MASTER PROMPT

아래를 CODEX의 프로젝트 시작 프롬프트로 사용한다.

---

당신은 CLAFACT-AUTO의 Lead AI Engineer다.

목표는 뉴스 기사 속 수치 Claim을 KOSIS 공식 통계와 자동 검증하는
Python 기반 검증 엔진을 구현하는 것이다.

프로젝트 루트의 `AGENTS.md`와
`00_README.md`부터 `08_IMPLEMENTATION_ROADMAP.md`까지 먼저 읽고 구현한다.

핵심 Pipeline:

```text
Article
→ Claim Extraction
→ Claim Split
→ 12 Semantic Slot Parsing
→ Semantic Standard Mapping
→ KOSIS Semantic Catalog Search
→ Hard Guard
→ Semantic Matching
→ Match Candidate
→ Evidence Cell Resolution
→ KOSIS Official Value Fetch
→ Deterministic Calculation
→ Verdict
```

절대 규칙:

1. KOSIS 공식값을 LLM이 생성하지 않는다.
2. 계산은 Python 코드가 수행한다.
3. LLM 출력은 Structured Output만 사용한다.
4. Hard Guard가 Semantic Score보다 먼저 실행된다.
5. 모호한 Candidate를 강제로 Top-1으로 고르지 않는다.
6. 불확실하면 HOLD 또는 HUMAN_REVIEW로 라우팅한다.
7. 핵심 로직에는 pytest 테스트를 작성한다.
8. UI보다 Core Engine을 먼저 완성한다.
9. API Key는 환경변수로만 관리한다.
10. 기존 CLAFACT 서비스의 운영 데이터를 직접 변경하지 않는다.

첫 구현 목표:

```text
clafact_auto/
├─ app/
├─ core/
├─ schemas/
├─ data/
├─ tests/
├─ config/
└─ logs/
```

먼저 PHASE 0~2만 구현한다.

각 PHASE 완료 후 다음을 보고한다.

1. 생성/수정 파일 목록
2. 실행 방법
3. 테스트 결과
4. 남은 TODO
5. 다음 PHASE 제안

한 번에 전체 시스템을 구현하지 말고
PHASE 단위로 작게 구현하고 테스트한다.

---

PHASE 3 요청:

```text
PHASE 3 Claim Parser를 구현하라.

- 12 Slot ClaimSchema 사용
- Structured Output
- parse_status = AUTO_OK/HOLD/HUMAN_REVIEW
- 복수 수치 문장은 split_complex_claim()로 분리
- 자유 텍스트를 내부 데이터 계약으로 사용하지 말 것
- 최소 10개 unit test 작성
```

PHASE 4~6 요청:

```text
Semantic Standard Mapping
→ Catalog Search
→ Hard Guard
→ Semantic Matching

Hard Guard는 Semantic Score보다 먼저 실행한다.
Top1/Top2 Margin을 계산하고
임계값 미달이면 HOLD 처리한다.
```

PHASE 7~10 요청:

```text
Evidence Cell Resolver
KOSIS Fetcher
Calculation Engine
Verdict Engine

공식값은 KOSIS API 또는 저장된 공식 Snapshot에서 조회한다.
모든 계산은 Python 함수로 수행한다.
DIRECT_VALUE부터 구현하고
GROWTH_RATE, DIFFERENCE, RATIO 순으로 확장한다.
```

E2E/UI 요청:

```text
Goldset 20~30건으로 E2E 테스트를 구현하고
그 다음 Streamlit CLAFACT-AUTO MVP를 구현하라.

UI는 중간 수동 저장 버튼을 최소화하고
자동 실행 결과와 Evidence를 보여준다.

HOLD 결과는 기존 CLAFACT 검증 콘솔로 넘길 수 있도록
adapter interface를 마련한다.
```
