# CLAFACT-AUTO Data Schemas

## ClaimSchema
### 공식 정의

CLAFACT-AUTO Claim은 뉴스 기사에 포함된 수치적 사실 주장 중, 하나의 통계지표를 대상으로 특정 시점·지역·모집단·세부 분류 등의 적용 범위와 주장값·단위·비교 기준·계산 의미를 구조화할 수 있으며, 원문 문장과 기사 기준일에 연결된 고유 정체성을 보존하고, 하나 이상의 KOSIS 공식 Evidence Cell과 하나의 결정론적 계산을 통해 하나의 최종 판정을 받을 수 있는 최소 검증 단위다. 하나의 계산과 판정으로 검증할 수 없는 서로 다른 지표·시점·지역·비교 기준·주장값은 별도 Claim으로 분리하고, 필수 정보나 공식 근거가 부족하면 임의로 확정하지 않고 사유가 명시된 HOLD로 보존한다.

```text
한 Claim = 한 검증 대상 + 한 주장값 + 한 계산 의미 + 한 최종 판정
```

### Claim 불변식

1. **단일 검증 대상:** 하나의 Claim에는 하나의 대상 통계지표만 존재한다.
2. **단일 주장값:** `value`와 `unit`은 최종적으로 검증할 하나의 기사 주장값을 나타낸다.
3. **단일 계산 의미:** `comparison`, `calculation`, `condition`은 하나의 결정론적 계산으로 해석되어야 한다.
4. **단일 판정:** 하나의 Claim은 정확히 하나의 `VerdictSchema`로 귀결된다.
5. **복수 Evidence 허용:** 계산에 필요한 KOSIS Evidence Cell은 하나 이상일 수 있다.
6. **출처 정체성 보존:** `ClaimRegistryRecord`의 `article_id`, `sentence_id`, `article_published_at`, `source_ref`와 Claim의 `claim_id`, `source_sentence`를 함께 보존한다.
7. **복합 주장 분리:** 서로 다른 지표·시점·지역·비교 기준·주장값은 각각 별도 Claim으로 분리한다.
8. **불확실성 보존:** 안전하게 분리하거나 필수 의미를 확정할 수 없으면 임의의 Top-1 해석을 만들지 않고 `HOLD` 또는 `HUMAN_REVIEW`로 라우팅한다.
9. **공식값 비생성:** Claim은 기사 주장만 표현하며 KOSIS 공식값을 포함하거나 LLM으로 생성하지 않는다.
10. **검증 책임 분리:** LLM은 12슬롯 구조화까지만 담당하고 Evidence 조회, 계산, 판정은 Python 파이프라인이 수행한다.

### 12 Semantic Slots와 메타데이터

`indicator`부터 `source_hint`까지가 의미 해석에 사용하는 12개 슬롯입니다. `claim_id`, `source_sentence`, `parse_status`, `parse_reason`은 출처 추적과 라우팅을 위한 Claim 메타데이터입니다. 12개 슬롯의 키는 Structured Output에서 항상 존재해야 하지만, 기사에서 확정할 수 없는 값은 `null`로 보존할 수 있습니다. `AUTO_OK` 허용 여부는 Claim 유형별 필수 슬롯 계약이 결정하며, 불충분한 Claim은 후속 KOSIS 후보를 강제로 선택하지 않습니다.

### 경계 예시

- `2024년 12월 취업자 수는 2,804만1천 명이었다.`는 하나의 직접값 Claim이다.
- `배추 물가는 전년 동월 대비 34.5% 하락했다.`는 현재·전년 Evidence 두 개를 사용하지만 하나의 증감률 Claim이다.
- `수출은 3% 증가했고 수입은 2% 감소했다.`는 지표와 주장값이 다르므로 두 Claim으로 분리한다.
- `서울 고용률은 70%, 부산은 68%였다.`는 지역과 주장값이 다르므로 두 Claim으로 분리한다.
- `내년 수출은 증가할 전망이다.`처럼 실적 수치가 아닌 전망은 자동 사실 검증 대상으로 확정하지 않는다.
- KOSIS에 대응하는 공식 통계가 없는 수치 Claim도 원문 Claim으로는 보존하되, 근거를 만들지 않고 적절한 단계에서 `HOLD`한다.

```python
class ClaimSchema(BaseModel):
    claim_id: str
    source_sentence: str
    indicator: str | None
    value: float | None
    unit: str | None
    time: str | None
    frequency: str | None
    region: str | None
    population: str | None
    dimension: dict | None
    comparison: dict | None
    calculation: str | None
    condition: dict | None
    source_hint: str | None
    parse_status: Literal["AUTO_OK", "HOLD", "HUMAN_REVIEW"]
    parse_reason: str | None
```

## StandardConceptSchema

```python
class StandardConceptSchema(BaseModel):
    concept_id: str
    canonical_name: str
    standard_key: str
    matched_alias: str | None
    status: Literal["MATCHED", "NEW_CANDIDATE", "UNRESOLVED"]
```

## KosisCandidateSchema

```python
class KosisCandidateSchema(BaseModel):
    org_id: str
    tbl_id: str
    tbl_name: str
    core_item_ids: list[str]
    core_item_names: list[str]
    dimension_ids: list[str]
    dimension_names: list[str]
    dimension_members: dict
    unit_names: list[str]
    frequency: str | None
    start_period: str | None
    end_period: str | None
    source_stat_id: str | None
    source_name: str | None
    metadata_status: str
```

## EvidenceCellSchema

```python
class EvidenceCellSchema(BaseModel):
    org_id: str
    tbl_id: str
    itm_id: str
    obj_id: str | None
    member_code: str | None
    prd_se: str
    prd_de: str
    unit: str | None
    canonical_key: str
    status: Literal["CONFIRMED", "UNRESOLVED", "AMBIGUOUS"]
```

## CalculationPlan

```python
class CalculationPlan(BaseModel):
    calculation_type: Literal[
        "DIRECT_VALUE",
        "DIFFERENCE",
        "GROWTH_RATE",
        "RATIO",
        "SHARE",
        "MULTIPLE",
        "RANK",
        "THRESHOLD"
    ]
    required_cells: list[EvidenceCellSchema]
    operator: str | None
    tolerance: float | None
```

## VerdictSchema

```python
class VerdictSchema(BaseModel):
    claim_id: str
    claim_value: float | None
    evidence_values: list[float]
    calculated_value: float | None
    verdict: Literal["MATCH", "MISMATCH", "UNDETERMINED"]
    route_status: Literal["AUTO", "HOLD", "HUMAN_REVIEW"]
    reason_code: str
    explanation: str
    evidence_cells: list[EvidenceCellSchema]
    dataset_version: str
    semantic_standard_version: str
    kosis_catalog_version: str
    matching_version: str
    calculation_version: str
```
