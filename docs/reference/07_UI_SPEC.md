# CLAFACT-AUTO Streamlit MVP UI Spec

## 목적

기존 CLAFACT처럼 중간마다 사람이 저장/선택하는 UI가 아니라,
입력 후 자동 실행되고 결과와 Evidence를 보여주는 UI.

## 좌측 메뉴

```text
CLAFACT-AUTO
- Auto Verify
- Batch Verify
- Hold Queue
- Goldset Test
- System Status
```

## Auto Verify

입력:
- 뉴스 문장
- 기사 본문

버튼:
`자동 검증 실행`

진행 단계:

```text
1. Claim Parsing
2. Semantic Standard
3. KOSIS Catalog Search
4. Hard Guard
5. Semantic Matching
6. Evidence Cell
7. KOSIS Fetch
8. Calculation
9. Verdict
```

## 결과 카드

```text
Verdict: 일치
Status: AUTO

Claim
2024년 경제성장률은 2%였다.

Standard Concept
C000014 / 경제성장률

KOSIS
DT_1YL20571 / 경제성장률(시도)

Evidence Cell
T10 / 전국 / 2024 / 연 / %

Official Value
2.0%

Calculation
DIRECT_VALUE

Result
2.0 = 2.0
```

## HOLD UI

- HOLD 이유
- Top Candidates
- Hard Guard 결과
- Semantic Score/Margin
- 기존 CLAFACT Review Console로 넘기는 버튼

## System Status

- Semantic Standard version
- KOSIS Catalog version
- Matcher version
- KOSIS API status
- Goldset pass rate
- Average latency
