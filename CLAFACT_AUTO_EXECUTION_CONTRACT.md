# CLAFACT-AUTO 최우선 실행 계약

> 이 문서는 CLAFACT-AUTO의 구현·수정·테스트·리뷰에서 가장 먼저 확인해야 하는 프로젝트 실행 계약이다. 모든 작업은 이 계약을 만족해야 하며, `AGENTS.md`의 다른 지침이나 하위 설계 문서와 충돌할 경우 이 계약을 우선 적용한다.

## 1. 서비스 목적

CLAFACT-AUTO는 새로운 뉴스에서 수치 Claim을 추출하고 12개 의미 슬롯으로 구조화한 뒤, Claim의 지표·시점·지역·대상·차원·비교·계산 조건을 이용해 KOSIS 공식 통계표와 정확한 Evidence 좌표를 찾고, 공식값과 공표정보를 직접 조회하여 Python 계산으로 판정하는 서비스다.

## 2. 최상위 불변식

```text
12슬롯 Claim
+ Semantic Standard
+ KOSIS 구조 정보
= KOSIS 공식 API 요청을 생성하기 위한 입력

공식값
+ 공표정보
= KOSIS 및 공식 작성기관에서 직접 조회한 검증 근거

최종 계산
= Python 결정론적 함수의 결과
```

구조화 데이터는 조회를 대신하는 답안이 아니다. 구조화의 목적은 새로운 Claim에 필요한 공식 통계표·항목·차원·기간을 찾아 실제 공식 조회를 수행하는 것이다.

## 3. 필수 실행 파이프라인

모든 신규 Claim은 다음 순서를 따른다.

```text
Article
→ Claim Extraction
→ Claim Split
→ 12 Slot Parsing
→ Semantic Standard Mapping
→ KOSIS Catalog API Search
→ KOSIS Official Metadata API
→ Hard Guard
→ Semantic Matching
→ Evidence Cell Resolution
→ KOSIS Official Value API
→ Official Publication Information Lookup
→ Deterministic Python Calculation
→ Verdict
```

Streamlit 단일 검증, 뉴스 배치 검증, Registry 재실행은 모두 같은 Core Engine과 같은 순서를 사용한다.

## 4. 직접 조회 계약

다음 단계는 실제 공식 조회를 수행해야 한다.

1. **통계표 검색**: Claim과 Concept 검색어로 KOSIS Catalog/Search API를 호출한다.
2. **공식 구조 확인**: 선택 후보의 ITM·PRD·분류·항목 메타데이터를 KOSIS API에서 조회한다.
3. **Evidence 좌표 확정**: Claim 슬롯과 공식 메타데이터를 결합해 표·항목·차원·기간 코드를 확정한다.
4. **공식값 조회**: 확정 좌표로 KOSIS Parameter API를 호출한다.
5. **공표정보 조회**: KOSIS 통계설명 API의 공표주기·공표시기·공표방법과 공식 작성기관의 발표정보를 조회한다.
6. **계산 및 판정**: 조회한 공식값만 Python 계산 함수에 전달한다.

API 키가 설정되어 있다는 표시만으로 조회 성공으로 간주하지 않는다. 각 단계는 실제 요청 결과와 상태를 실행 추적에 남겨야 한다.

## 5. 공표정보 계약

공표정보도 공식값과 같은 실행 과정에서 동적으로 확인한다.

- KOSIS 통계설명 API의 `pubPeriod`, `pubDate`, `publictMth`를 조회한다.
- 필요한 경우 공식 작성기관의 발표 페이지에서 대상 기간과 게시일을 확인한다.
- KOSIS 값 응답의 `LST_CHN_DE`는 최종수정일로 취급하며, 단독으로 최초 공표일이라고 해석하지 않는다.
- 확인한 공표 근거는 출처 URL·조회시각·내용 해시와 함께 자동 보존한다.
- 보존된 자료는 재현성과 감사에 사용하며, 신규 Claim의 공식 조회를 생략하는 근거로 사용하지 않는다.

## 6. HOLD 계약

`HOLD`는 다음 조건을 모두 만족할 때만 허용한다.

1. 해당 단계의 공식 조회를 실제로 시도했다.
2. 재시도·대체 공식 경로 등 정해진 조회 절차를 수행했다.
3. 자동 판정에 필요한 공식 근거가 여전히 부족하다.
4. 실패 단계와 안정적인 reason code를 기록했다.
5. “공식 통계가 없음”과 “외부 조회 실패”를 구분했다.

다음 상태는 서로 다른 의미로 보존한다.

| 상태 | 의미 |
| --- | --- |
| `CONCEPT_NOT_FOUND` | Claim의 통계 의미를 하나로 확정하지 못함 |
| `KOSIS_CATALOG_UNAVAILABLE` | 공식 통계표 검색 요청을 완료하지 못함 |
| `KOSIS_METADATA_UNAVAILABLE` | 공식 구조 메타데이터 요청을 완료하지 못함 |
| `NO_EVIDENCE_COORDINATE_CANDIDATE` | 공식 구조를 조회했지만 Claim 조건을 만족하는 좌표를 확정하지 못함 |
| `FETCH_FAILED` | 확정 좌표의 공식값 요청을 완료하지 못함 |
| `AS_OF_UNAVAILABLE` | 공식 공표정보 조회 후에도 기사시점 이용 가능성을 확인하지 못함 |

공식 조회를 수행하지 않은 상태에서 위 reason code를 생성해서는 안 된다.

## 7. 금지되는 구현

- LLM이 KOSIS 공식값·공표일·계산 결과를 생성하거나 추정하는 구현
- 특정 Claim 문장·Claim ID·지표명을 조건으로 결과를 반환하는 운영 코드
- 테스트용 고정 응답을 운영 판정 경로에서 사용하는 구현
- 의미 유사도만으로 공식 좌표를 확정하는 구현
- Hard Guard보다 Semantic Score를 먼저 적용하는 구현
- 공식 조회 실패를 “후보 없음” 또는 “통계 없음”으로 바꾸는 구현
- 조회를 수행하지 않고 등록 여부만으로 `AUTO` 또는 `HOLD`를 결정하는 구현
- 단일 성공 사례를 전체 파이프라인 완성으로 보고하는 행위

## 8. 테스트 및 완료 조건

기능이 완성됐다고 보고하려면 다음 증거가 필요하다.

1. 신규 뉴스 문장이 12슬롯 Claim으로 구조화된다.
2. Claim 문맥으로 Semantic Concept이 확정된다.
3. 실제 KOSIS Catalog와 공식 메타데이터 조회가 실행된다.
4. 공식 메타데이터로 Evidence 좌표가 확정된다.
5. 실제 KOSIS 공식값 API 응답이 수집된다.
6. 공식 공표정보 조회가 실행된다.
7. Python 계산 결과와 Verdict가 생성된다.
8. 공식값 출처·좌표·응답 해시·공표 근거가 결과에 남는다.
9. 단일 UI와 배치가 같은 결과 계약을 사용한다.
10. 실패 시 실제 실패 단계의 reason code로 `HOLD`된다.

단위 테스트의 mock 성공만으로 운영 E2E 완료를 선언하지 않는다. Release acceptance에는 실제 공식 API를 통과하는 신규 Claim 검증이 포함되어야 한다.

## 9. 작업 시작 전 체크리스트

모든 구현 작업은 시작 전에 다음을 확인한다.

- [ ] 이 변경은 새로운 Claim의 공식 조회 경로를 확장하는가?
- [ ] 실제 KOSIS API 호출이 어느 단계에서 실행되는가?
- [ ] Claim 12슬롯과 Semantic Standard가 API 요청 파라미터로 연결되는가?
- [ ] 공식 메타데이터가 Evidence 좌표에 반영되는가?
- [ ] 공식값과 공표정보가 직접 조회되는가?
- [ ] Python만 계산과 판정을 수행하는가?
- [ ] 공식 조회 후에만 HOLD가 결정되는가?
- [ ] 특정 사례가 아닌 동일 유형의 신규 Claim에 반복 적용되는가?

하나라도 충족하지 못하면 구현 방향을 재검토한다.

