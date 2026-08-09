# CLAFACT-AUTO System Architecture

```text
NEWS INPUT
  ↓
Claim Classifier
  ↓
Claim Splitter
  ↓
12 Slot Parser
  ↓
Semantic Standard
  ↓
KOSIS Semantic Catalog
  ↓
Candidate Search
  ↓
Hard Guard
  ↓
Semantic Matching
  ↓
Match Candidate
  ↓
Evidence Resolver
  ↓
Evidence Cell
  ↓
KOSIS Fetcher
  ↓
Calculator
  ↓
Verdict Engine
  ↓
AUTO RESULT / HOLD / HUMAN_REVIEW
```

## 계층

### Interpretation Layer
- Claim Classifier
- Claim Splitter
- 12 Slot Parser
- Semantic Normalizer

### Retrieval Layer
- KOSIS Semantic Catalog
- Candidate Search
- Hard Guard
- Semantic Matcher

### Evidence Layer
- Evidence Resolver
- KOSIS Fetcher
- Snapshot/Audit

### Verification Layer
- Calculator
- Verdict Engine

### Review Layer
- HOLD
- HUMAN_REVIEW
- 기존 CLAFACT 검증 콘솔

## 실패 경로

```text
API 실패 → FETCH_ERROR → HOLD
Evidence Cell 불확정 → CELL_UNRESOLVED → HOLD
Candidate 모호 → AMBIGUOUS_MATCH → HUMAN_REVIEW
```
