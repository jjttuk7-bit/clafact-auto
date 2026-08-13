# Contextual Semantic Mapping Design

## Goal

CLAFACT-AUTO가 `indicator`만으로 Concept를 선택하지 않고 12슬롯의 dimension 문맥을 결합해 공식 Semantic Standard를 결정하고, 그 Concept의 KOSIS 검색어로 공식 표·항목·차원 좌표를 찾도록 한다. `UNRESOLVED`는 성공으로 기록하지 않으며 Semantic Mapping 단계에서 HOLD한다.

## Approved data flow

1. Claim 원본 슬롯은 변경하지 않는다.
2. Semantic Mapper가 `indicator`와 dimension member를 조합한 후보 라벨을 생성한다.
3. 가장 구체적인 복합 라벨을 먼저 exact/normalized match하고, 이후 기존 indicator-only 규칙으로 후퇴한다.
4. 운영 Semantic Standard Registry에 CPI 상세 Concept와 공식 KOSIS 검색어를 버전형 데이터로 등록한다.
5. 매핑된 Concept의 `kosis_search_terms`와 Claim dimension을 사용해 KOSIS Catalog를 검색한다.
6. Concept가 `UNRESOLVED`면 Catalog Search를 실행하지 않고 `SEMANTIC_MAPPING` HOLD를 반환한다.
7. 매핑된 경우에만 Catalog → Hard Guard → Evidence → Official Value → Python Verdict를 진행한다.

## Generalization boundary

`물가 + 배추 → 배추 물가`는 복합 라벨 생성 규칙의 한 사례다. 코드에 배추 전용 분기를 두지 않는다. 품목, 성별, 산업, 연령 등 모든 dimension member는 동일한 방식으로 indicator와 결합된다. 공식 Concept ID·별칭·KOSIS 검색어는 코드가 아니라 Semantic Standard 데이터에서 관리한다.

## CPI detail standard

- Concept ID: `CPI_DETAIL:A02A01701`
- Canonical name: `배추 소비자물가지수`
- Standard key: `cpi_detail:A02A01701`
- Alias: `배추 물가`
- KOSIS search terms: `배추 소비자물가지수`, `품목별 소비자물가지수 배추`
- Expected official table: `DT_1J22112`
- Expected item/member coordinates: `ITM=T`, `C1=T10`, `C2=A02A01701`

## Safety and trace contract

- 복합 라벨이 여러 Concept에 매칭되면 강제 Top-1을 선택하지 않는다.
- `UNRESOLVED` Concept는 `SEMANTIC_MAPPING / HOLD / CONCEPT_NOT_FOUND`로 기록한다.
- Semantic Mapping PASS는 `concept.status == MATCHED`일 때만 기록한다.
- KOSIS 공식값은 LLM이 생성하지 않으며 Evidence 좌표가 확정된 뒤 Python 계산만 수행한다.

## Acceptance criteria

- 배추 Claim의 원본 `indicator=물가`, `dimension.product=배추`는 그대로 보존된다.
- Semantic Mapping 결과는 `CPI_DETAIL:A02A01701`이다.
- KOSIS 검색어에 두 공식 문구가 포함된다.
- 동적 E2E가 `DT_1J22112`의 202510·202410 Evidence를 사용한다.
- Python 계산값이 약 `-34.4968%`가 되어 Claim `-34.5%`와 MATCH/AUTO를 반환한다.
- 미등록 dimension+indicator는 Semantic Mapping HOLD로 끝난다.

