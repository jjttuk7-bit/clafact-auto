# Claim Registry

뉴스 원천 문장과 12슬롯 ClaimSchema를 함께 보존하는, 재현 가능한 검증 요구 목록이다.
Registry의 수치는 KOSIS 공식값이 아니며, KOSIS 공식값·좌표·계산 결과를 생성하거나 대체하지 않는다.

## 생성된 기준선

| Registry | 원천 | 실제 건수 | 기대 건수 | 상태 |
| --- | --- | ---: | ---: | --- |
| `kosis_target_1600_v1` | 통합 원본의 `03_KOSIS대상_1600건` 탭 | 1,600 | 1,600 | 일치 |
| `semantic_guard_recheck_v2_2_1` | Guard 재검증 구조화 CSV | 1,531 | 1,532 | 1건 차이 확인 필요 |

각 디렉터리에는 다음 두 파일이 있다.

- `claim_registry.jsonl`: 한 줄당 하나의 `ClaimRegistryRecord`. 원천 식별자, 기사일자, 원천 메타데이터와 12슬롯 Claim을 보존한다.
- `validation_report.json`: 기대 건수·실제 건수·중복 여부를 기록한다.

## 1,532건 목표에 대한 원칙

현재 확인된 원천은 1,600건, 기존 구조화 Guard 재검증 파일은 1,531건이다. 따라서 이 프로젝트는 존재하지 않는 한 건을 생성하거나 1,531건을 1,532건으로 표기하지 않는다. 누락한 하나의 원천 `article_id`/`sentence_id`를 확정한 뒤에만 최종 1,532건 Registry를 선언한다.

## 재생성 명령

```powershell
python -m tools.build_claim_registry `
  --input "<통합파일.xlsx>" `
  --sheet-name "03_KOSIS대상_1600건" `
  --header-row 3 `
  --article-input "<통합파일.xlsx>" `
  --article-sheet-name "01_전처리_기사요약" `
  --article-header-row 3 `
  --source-ref "kosis-target-1600-v1" `
  --expected-count 1600 `
  --output-dir "data/claim_registry/kosis_target_1600_v1"
```

`tools/build_claim_registry.py`는 CSV와 XLSX를 모두 지원한다. XLSX에서는 원천 탭 이름과 헤더 행을 명시해야 하며, 기사일자 탭은 선택적으로 결합한다.

## 다음 작업

1. 1,531↔1,532 차이의 누락 원천을 확정한다.
2. `comparison`, `calculation`, `condition`을 포함한 12슬롯 완성도를 높인다.
3. 후보 통계표, Hard Guard 결과, Evidence 좌표, 공식 Snapshot 버전을 Registry와 연결한다.
