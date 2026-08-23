# Multi-Claim Role Grouping Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 문장 속 숫자의 역할을 먼저 분류해 실제로 독립된 Claim만 생성하고, 고용 대표 20건의 기대 결과·실제 결과·12개 항목·재입장 결과를 CSV로 남긴다.

**Architecture:** 기존 정규식은 수치 표현을 빠짐없이 찾는 역할만 담당한다. 외부 모델은 제한된 Structured Output으로 각 수치의 역할과 소속 Claim 묶음을 제안하고, Python 검증기가 수치 누락·중복·원문 불일치·잘못된 중심 수치를 차단한다. 검증된 묶음의 중심 수치만 기존 12개 항목 추출과 Admission 경로에 전달하며, 불확실한 묶음은 공식 조회 전에 멈춘다.

**Tech Stack:** Python 3.12+, Pydantic v2, OpenAI Responses API/HCX Structured Output adapters, pytest, CSV/JSONL 감사 기록

---

### Task 1: 수치 발견과 역할 묶음 계약 분리

**Files:**
- Create: `schemas/claim_group.py`
- Modify: `core/targeted_claim_splitter.py`
- Test: `tests/unit/test_claim_group_schema.py`
- Test: `tests/unit/test_targeted_claim_splitter.py`

**Step 1: Write the failing tests**

다음 계약을 먼저 테스트한다.

```python
def test_discovers_mentions_without_creating_children() -> None:
    mentions = discover_numeric_mentions(
        "고용률은 60%로 전년 58%보다 2%포인트 올랐다."
    )
    assert [m.mention_id for m in mentions] == ["n1", "n2", "n3"]
    assert [m.expression for m in mentions] == ["60%", "58%", "2%포인트"]


def test_group_plan_requires_one_main_value_per_claim_group() -> None:
    with pytest.raises(ValidationError):
        ClaimGroupingPlan.model_validate({
            "status": "READY",
            "assignments": [
                {"mention_id": "n1", "role": "REFERENCE_VALUE", "group_id": "g1"}
            ],
            "groups": [{"group_id": "g1", "main_mention_id": "n1"}],
        })
```

역할 enum은 `MAIN_VALUE`, `REFERENCE_VALUE`, `CHANGE_VALUE`, `EQUIVALENT_VALUE`, `CONTEXT_VALUE`만 허용한다. `READY` 계획은 그룹마다 정확히 하나의 `MAIN_VALUE`를 요구한다.

**Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_claim_group_schema.py tests/unit/test_targeted_claim_splitter.py -q`

Expected: 새 schema/import 부재로 FAIL.

**Step 3: Write minimal implementation**

`schemas/claim_group.py`에 `NumericRole`, `NumericAssignment`, `ClaimGroup`, `ClaimGroupingPlan`을 Pydantic 모델로 만든다. `targeted_claim_splitter.py`에는 기존 정규식을 재사용하는 `discover_numeric_mentions()`를 만들고, 기존 `build_targeted_claim_inputs()`는 호환용 wrapper로 유지한다.

```python
class NumericMention(BaseModel):
    mention_id: str
    expression: str
    start: int
    end: int


def discover_numeric_mentions(source_sentence: str) -> list[NumericMention]:
    # 정규식 결과를 위치순으로 정렬하고 같은 span만 제거한다.
    ...
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_claim_group_schema.py tests/unit/test_targeted_claim_splitter.py -q`

Expected: PASS.

**Step 5: Commit**

```bash
git add schemas/claim_group.py core/targeted_claim_splitter.py tests/unit/test_claim_group_schema.py tests/unit/test_targeted_claim_splitter.py
git commit -m "feat: define numeric role grouping contract"
```

### Task 2: Python 안전 검사 구현

**Files:**
- Create: `core/claim_group_validator.py`
- Test: `tests/unit/test_claim_group_validator.py`

**Step 1: Write the failing tests**

다음을 각각 음성 테스트로 만든다.

- 발견된 수치 ID가 하나라도 빠짐
- 존재하지 않는 수치 ID를 반환함
- 한 수치를 두 그룹에 배정함
- 그룹 중심 수치가 `MAIN_VALUE`가 아님
- `CONTEXT_VALUE`만으로 자식 Claim을 만듦
- 같은 그룹에 중심 수치가 두 개임
- `status=HUMAN_REVIEW`인데 그룹을 자동 실행하려 함

정상 테스트는 `60%/58%/2%포인트`가 한 그룹으로, 서로 다른 지표 두 개가 두 그룹으로 통과하는지 확인한다.

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_claim_group_validator.py -q`

Expected: validator 부재로 FAIL.

**Step 3: Write minimal implementation**

```python
@dataclass(frozen=True, slots=True)
class ValidatedClaimGroup:
    group_id: str
    main_expression: str
    supporting_expressions: tuple[tuple[str, NumericRole], ...]


def validate_grouping_plan(
    mentions: list[NumericMention],
    plan: ClaimGroupingPlan,
) -> GroupValidationResult:
    # 모든 mention을 정확히 한 번 설명해야 한다.
    # CONTEXT_VALUE는 group_id 없이 허용한다.
    # READY가 아니거나 모순이 있으면 groups를 비워 fail-closed 한다.
    ...
```

실패 사유는 `GROUPING_MENTION_MISSING`, `GROUPING_UNKNOWN_MENTION`, `GROUPING_DUPLICATE_ASSIGNMENT`, `GROUPING_MAIN_VALUE_INVALID`, `GROUPING_AMBIGUOUS`로 고정한다.

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_claim_group_validator.py -q`

Expected: PASS.

**Step 5: Commit**

```bash
git add core/claim_group_validator.py tests/unit/test_claim_group_validator.py
git commit -m "feat: validate claim role groups fail closed"
```

### Task 3: 외부 Structured Output 묶음 제안기 연결

**Files:**
- Create: `core/claim_group_output_contract.py`
- Create: `core/openai_claim_grouper.py`
- Create: `core/hcx_claim_grouper.py`
- Modify: `core/openai_function_claim_extractor.py`
- Modify: `core/hcx_claim_extractor.py`
- Modify: `core/hcx_function_claim_extractor.py`
- Modify: `core/fallback_claim_extractor.py`
- Test: `tests/unit/test_openai_claim_grouper.py`
- Test: `tests/unit/test_hcx_claim_grouper.py`
- Test: `tests/unit/test_fallback_claim_extractor.py`

**Step 1: Write the failing tests**

OpenAI와 HCX 요청이 원문과 `n1..nN` 수치 목록만 전달하고, 응답이 정확히 한 개의 schema-constrained 결과여야 함을 검증한다. 잘못된 역할, 중복 ID, 자유 텍스트 응답은 contract error가 되어야 한다. `FallbackClaimExtractor.group_claims()`는 일시 오류일 때만 보조 제공자를 사용해야 한다.

**Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_openai_claim_grouper.py tests/unit/test_hcx_claim_grouper.py tests/unit/test_fallback_claim_extractor.py -q`

Expected: grouper 부재로 FAIL.

**Step 3: Write minimal implementation**

각 production extractor에 다음 메서드를 추가한다.

```python
def group_claims(
    self,
    source_sentence: str,
    mentions: list[NumericMention],
) -> ClaimGroupingPlan:
    ...
```

지침은 “통계값을 만들지 말 것, 제공된 mention ID만 사용할 것, 비교값·증감값·환산값은 같은 중심 Claim에 묶을 것, 지표가 다를 때만 그룹을 나눌 것, 불명확하면 HUMAN_REVIEW”로 제한한다. 출력은 Pydantic JSON schema 또는 강제 function call 한 개로 검증한다.

**Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_openai_claim_grouper.py tests/unit/test_hcx_claim_grouper.py tests/unit/test_fallback_claim_extractor.py -q`

Expected: PASS.

**Step 5: Commit**

```bash
git add core/claim_group_output_contract.py core/openai_claim_grouper.py core/hcx_claim_grouper.py core/openai_function_claim_extractor.py core/hcx_claim_extractor.py core/hcx_function_claim_extractor.py core/fallback_claim_extractor.py tests/unit/test_openai_claim_grouper.py tests/unit/test_hcx_claim_grouper.py tests/unit/test_fallback_claim_extractor.py
git commit -m "feat: add structured numeric role grouping adapters"
```

### Task 4: v3 재분리와 12개 항목 재입장 연결

**Files:**
- Modify: `core/admission_recovery_v3.py`
- Modify: `core/targeted_claim_splitter.py`
- Test: `tests/unit/test_admission_recovery_v3.py`
- Test: `tests/unit/test_contextual_targeted_recovery.py`

**Step 1: Replace the old expected behavior with failing tests**

```python
def test_comparison_numbers_form_one_child() -> None:
    source = "고용률은 60%로 전년 58%보다 2%포인트 올랐다."
    result = recover_registry_record_v3(...)
    assert len(result.entries) == 1
    assert result.entries[0].record.slot_enrichment["numeric_roles"] == {
        "60%": "MAIN_VALUE",
        "58%": "REFERENCE_VALUE",
        "2%포인트": "CHANGE_VALUE",
    }


def test_two_independent_indicators_form_two_children() -> None:
    result = recover_registry_record_v3(...)
    assert len(result.entries) == 2


def test_ambiguous_grouping_never_calls_official_service() -> None:
    result = recover_registry_record_v3(...)
    assert result.entries[0].admission_route == "STRUCTURAL_HOLD"
    assert service.claims == []
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_admission_recovery_v3.py tests/unit/test_contextual_targeted_recovery.py -q`

Expected: 기존 숫자별 child 동작 때문에 FAIL.

**Step 3: Write minimal implementation**

`recover_registry_record_v3()`는 수치가 두 개 이상이면 extractor의 `group_claims()`를 호출하고 즉시 `validate_grouping_plan()`을 거친다. 검증된 그룹마다 중심 수치 하나와 supporting expressions를 포함한 JSON 입력을 만들어 기존 `parse_claim`을 호출한다. 자식 ID는 원문과 group의 모든 mention ID로 결정적으로 생성한다. `slot_enrichment`에는 전체 역할표, 그룹 ID, 중심 수치, 보조 수치, 검증 사유를 남긴다. grouping 기능이 없는 테스트 extractor는 명시적 legacy adapter를 쓰게 하며 production에서는 묶음 제안 없이 숫자별 자동 승격하지 않는다.

**Step 4: Run focused and compatibility tests**

Run: `pytest tests/unit/test_admission_recovery_v3.py tests/unit/test_contextual_targeted_recovery.py tests/unit/test_admission_recovery_batch_v3.py -q`

Expected: PASS.

**Step 5: Commit**

```bash
git add core/admission_recovery_v3.py core/targeted_claim_splitter.py tests/unit/test_admission_recovery_v3.py tests/unit/test_contextual_targeted_recovery.py
git commit -m "feat: recover one child per validated claim group"
```

### Task 5: 고용 대표 20건 골드 CSV와 결과 기록 확장

**Files:**
- Create: `tests/goldset/multi_claim_employment_20.csv`
- Modify: `core/issue_group_executor.py`
- Create: `tools/run_multi_claim_group.py`
- Test: `tests/unit/test_multi_claim_group_csv.py`
- Test: `tests/integration/test_multi_claim_employment_goldset.py`

**Step 1: Freeze the 20 source cases**

`artifacts/clafact_final_completion_202608/claim_issue_master.csv`와 `01_source_registry.jsonl`을 읽기 전용으로 대조해 고용 분야 20건을 고른다. 골드 CSV에는 원문, 기대 수치 역할표, 기대 자식 수, 기대 경로를 사람이 확인해 기록한다. 사용자 소유 원본 artifact는 수정하지 않는다.

**Step 2: Write failing CSV tests**

결과 CSV가 다음 열을 반드시 갖는지 검사한다.

```text
기사번호,문장번호,부모Claim번호,원문,발견수치,
기대역할표,실제역할표,기대자식수,실제자식수,분리판정,
자식Claim번호,12개항목상태,재입장결과,중단사유,
코드버전,자료버전,실행시각
```

**Step 3: Run tests to verify they fail**

Run: `pytest tests/unit/test_multi_claim_group_csv.py tests/integration/test_multi_claim_employment_goldset.py -q`

Expected: runner/columns 부재로 FAIL.

**Step 4: Implement bounded runner**

`tools/run_multi_claim_group.py`는 골드 CSV의 정확히 20개 ID만 불러오며 `--limit` 최대값을 20으로 잠근다. 전체 Registry 입력이나 wildcard 입력을 거부한다. 실행 전 결과 CSV에 기대값을 복사하고, 실행 후 실제 역할·자식 수·12개 항목·재입장 결과를 병합한다.

**Step 5: Run tests to verify they pass**

Run: `pytest tests/unit/test_multi_claim_group_csv.py tests/integration/test_multi_claim_employment_goldset.py -q`

Expected: PASS.

**Step 6: Commit**

```bash
git add tests/goldset/multi_claim_employment_20.csv core/issue_group_executor.py tools/run_multi_claim_group.py tests/unit/test_multi_claim_group_csv.py tests/integration/test_multi_claim_employment_goldset.py
git commit -m "feat: add bounded employment multi-claim gold harness"
```

### Task 6: 외부 Structured Output으로 20건 실행 및 실패 수정

**Files:**
- Create: `artifacts/clafact_final_completion_202608/issue_group_harness/runs/multi-claim-employment-001.csv`
- Create: `artifacts/clafact_final_completion_202608/issue_group_harness/runs/multi-claim-employment-001.jsonl`
- Modify only if a repeated root cause is proven: files from Tasks 1–5 and their focused tests

**Step 1: Run exactly 20 cases**

Run:

```bash
python tools/run_multi_claim_group.py \
  --goldset tests/goldset/multi_claim_employment_20.csv \
  --registry artifacts/clafact_final_completion_202608/01_source_registry.jsonl \
  --output artifacts/clafact_final_completion_202608/issue_group_harness/runs/multi-claim-employment-001.csv \
  --limit 20
```

Expected: 전체 Registry 실행 없이 20건만 처리하며 CSV/JSONL 생성.

**Step 2: Evaluate**

다음을 집계한다.

- 기대 자식 수 일치율
- Claim 누락 수
- 불필요한 Claim 수
- 잘못된 자동 통과 수
- 12개 항목 완료 수
- 재입장 성공 수
- 검토 대상 수와 정확한 사유
- 외부 Structured Output 호출 수

**Step 3: Fix only repeated root causes with TDD**

같은 원인이 2건 이상 반복될 때만 음성 회귀 테스트를 먼저 추가하고 최소 수정한다. 개별 문장 하드코딩은 금지한다.

**Step 4: Re-run the same 20 once**

Expected: 완료 기준을 모두 충족하거나, 남은 실패가 정확한 유형·사유로 CSV에 기록됨. 완료 기준 미달이면 50건으로 확대하지 않는다.

**Step 5: Commit auditable results**

```bash
git add artifacts/clafact_final_completion_202608/issue_group_harness/runs/multi-claim-employment-001.csv artifacts/clafact_final_completion_202608/issue_group_harness/runs/multi-claim-employment-001.jsonl
git commit -m "test: record employment multi-claim group results"
```

### Task 7: 회귀 검사와 완료 판정

**Files:**
- Modify if needed: `docs/plans/2026-08-23-multi-claim-role-grouping-design.md`
- Create: `artifacts/clafact_final_completion_202608/issue_group_harness/runs/multi-claim-employment-001-summary.txt`

**Step 1: Run focused suite**

Run: `pytest tests/unit/test_claim_group_schema.py tests/unit/test_claim_group_validator.py tests/unit/test_openai_claim_grouper.py tests/unit/test_hcx_claim_grouper.py tests/unit/test_admission_recovery_v3.py tests/unit/test_multi_claim_group_csv.py tests/integration/test_multi_claim_employment_goldset.py -q`

Expected: PASS.

**Step 2: Run full automated suite**

Run: `pytest -q`

Expected: 모든 테스트 PASS. 전체 1,542건 외부 실행은 하지 않는다.

**Step 3: Verify repository state**

Run: `git status --short` and `git diff --check`

Expected: 사용자 소유 untracked artifacts 외 예상하지 못한 변경 없음, whitespace error 없음.

**Step 4: Write completion summary**

요약에는 20건 결과 수치, 남은 실패 유형, 50건 확대 가능 여부, 전체 실행을 하지 않았다는 사실을 쉬운 한국어로 기록한다.

**Step 5: Commit and push**

```bash
git add docs/plans/2026-08-23-multi-claim-role-grouping-design.md artifacts/clafact_final_completion_202608/issue_group_harness/runs/multi-claim-employment-001-summary.txt
git commit -m "docs: report multi-claim employment gate"
git push origin codex/final-completion-execution
```

## 실행 제한

- 이 계획 중 전체 1,542건 외부 실행은 금지한다.
- 20건 완료 기준을 통과하기 전 50건으로 확대하지 않는다.
- 원문 또는 특정 Claim ID를 위한 예외 하드코딩을 금지한다.
- 외부 모델 결과만 믿고 자식 Claim을 자동 통과시키지 않는다.
- 공식 KOSIS 값 생성이나 계산을 외부 모델에 맡기지 않는다.
