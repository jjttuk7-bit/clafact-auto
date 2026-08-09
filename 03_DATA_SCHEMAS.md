# CLAFACT-AUTO Data Schemas

## ClaimSchema

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
