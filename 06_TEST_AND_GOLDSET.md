# CLAFACT-AUTO Test & Goldset Plan

## 단계별 테스트

최종 Verdict만 보지 않는다.

```text
Claim Parsing
Concept Mapping
Candidate Search
Hard Guard
Semantic Matching
Evidence Cell
KOSIS Fetch
Calculation
Verdict
```

## 초기 Goldset

20~30건.

## Goldset 샘플

```json
{
  "claim_id": "G001",
  "sentence": "...",
  "expected_claim_slots": {},
  "expected_concept_id": "C000014",
  "expected_tbl_id": "DT_1YL20571",
  "expected_cell": {},
  "expected_value": 2.0,
  "expected_calculation": "DIRECT_VALUE",
  "expected_verdict": "MATCH"
}
```

## 평가 지표

Claim Parsing:
- slot accuracy
- missing slot rate
- AUTO_OK precision

Concept Mapping:
- concept accuracy
- unresolved rate

Hard Guard:
- false reject
- missed conflict

Semantic Matching:
- Top1 accuracy
- Top3 recall
- Margin distribution

Evidence Cell:
- exact cell accuracy

Verdict:
- MATCH precision
- MISMATCH precision
- UNDETERMINED recall

## 회귀 테스트

```bash
pytest tests/unit
pytest tests/integration
pytest tests/goldset
```

AUTO 판정은 recall보다 precision 우선.
