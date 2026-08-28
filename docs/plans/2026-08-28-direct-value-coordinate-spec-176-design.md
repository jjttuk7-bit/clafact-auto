# 직접값 미해결 176건 KOSIS 검색 명세 및 전수 평가 설계

## 목적

8번 직접값 원장 230건에서 공식 판정 완료, 검증 제외, 다른 유형 이동을 제외한 미해결 176건을 개별 예외 없이 동일한 검색 명세로 변환한다. 변환 가능한 Claim은 기존 `unified_claim_pipeline`과 v3 공식 엔진으로 실제 KOSIS Catalog·Metadata·Value·Publication API를 실행하고, 변환 불가능한 Claim도 중단 단계와 원인을 같은 176행 평가 원장에 남긴다.

## 검토한 접근

1. 실패 사유별 Claim 예외 규칙 추가
   - 빠르게 몇 건을 통과시킬 수 있지만 신규 뉴스에 일반화되지 않고 Claim ID·문장별 규칙이 누적된다.
2. 176건 전용 좌표 파이프라인 신설
   - 기존 Streamlit·배치·CLI와 결과 계약이 갈라져 실행계약을 위반할 위험이 크다.
3. 기존 통합 파이프라인 앞에 공통 KOSIS 검색 명세 계층 추가
   - Claim을 공식 검색 조건으로 표준화하되 실제 후보 검색·좌표 확정·값 조회는 기존 v3 공식 엔진이 수행한다.

3번을 채택한다.

## 범위 고정

최신 230행 원장에서 다음을 제외한다.

- 어떤 실행 단계에서든 엄격한 공식 판정 완료가 확인된 21건
- 공식통계 검증 대상이 아닌 28건
- 다른 검증 유형으로 이동한 4건
- 복수 기간 Claim 분리 단계로 이동한 1건

남은 176건을 목표 범위로 고정한다. Claim ID, 원문 해시, 입력 원장 해시, 코드·데이터 파일 해시를 manifest에 보존한다.

## KOSIS 검색 명세

각 Claim은 다음 필드로 변환한다.

- `claim_id`: 원장 Claim 식별자
- `indicator`: 원문에 근거한 구체 지표
- `measure_family`: 인원·금액·비율·수량·지수·면적 등 측정값 종류
- `value`, `unit`, `unit_family`, `scale`: 기사값과 단위·배율
- `period`, `frequency`, `period_mode`: 단일시점·누계·분기 등 기간 조건
- `region`, `geography_scope`: 전국·지역·국가 조건
- `dimensions`: 연령·성별·품목·산업·교역상대국 등 좌표 제약
- `calculation`, `required_evidence_cells`: 직접값에 필요한 공식값 수
- `official_route`: KOSIS 우선 또는 등록된 공식 작성기관 보조 경로
- `readiness_status`, `readiness_reasons`: 공식 검색 투입 가능 여부와 부족한 조건
- `search_terms`: 지표·대상·차원을 결합한 일반 검색어

명세 생성기는 기사에 없는 값이나 공식 좌표를 추정하지 않는다. 시점·대상·수치가 원문과 기사 작성일로 확정되지 않으면 `PRE_VERIFICATION`으로 남긴다.

## 실행 흐름

```text
230행 최신 원장
→ 미해결 직접값 176건 범위 고정
→ 원장 슬롯을 ClaimRegistryRecord로 재구성
→ 원문 기반 공통 보정
→ KOSIS 검색 명세 생성
→ 준비 완료 Claim은 unified_claim_pipeline에 투입
→ v3 공식 엔진의 Catalog API 검색
→ Official Metadata API 구조 확인
→ Hard Guard
→ Evidence 좌표 확정
→ Official Value API 조회
→ 공표정보 조회
→ Python 판정
→ 176행 단계별 평가 원장
```

## 공식 구조정보 색인

별도의 답안 DB나 고정 좌표를 만들지 않는다. 한 실행 안에서 KOSIS Catalog·Metadata API 응답을 표·항목·주기·지역·차원·단위별로 색인하고 같은 공식 표를 반복 조회하지 않도록 캐시한다. 색인은 후보 탐색을 빠르게 하는 실행 자료이며 신규 Claim도 같은 공식 API 요청을 먼저 수행한다.

## 평가 기준

176건 모두 정확히 한 행을 가져야 한다.

- 검색 명세 생성 성공률
- 공식 검색 진입률
- Concept 확정률
- Catalog 후보 발견률
- 공식 Metadata 확인률
- Hard Guard 통과율
- Evidence 좌표 확정률
- 공식값 조회율
- 공표정보 확인률
- 최종 판정률
- 단계별 HOLD 사유와 API 호출 수

기존 `RULE_DISCOVERY`, `INTERMEDIATE_VALIDATION`, `FINAL_BLIND` 구분을 보존하여 최종 미사용 집합의 성능을 별도 집계한다. 완료 수만 보고하지 않고 단계별 분모를 명시한다.

## 실패 처리

- 공식 조회 전 부족: `PRE_VERIFICATION`과 구체적인 슬롯 사유
- Catalog 요청 실패: `KOSIS_CATALOG_UNAVAILABLE`
- Metadata 요청 실패: `KOSIS_METADATA_UNAVAILABLE`
- 공식 구조를 조회했으나 좌표 없음: `NO_EVIDENCE_COORDINATE_CANDIDATE`
- 값 요청 실패: `FETCH_FAILED`
- 기사시점 공표 확인 불가: `AS_OF_UNAVAILABLE`

공식 API 미실행 상태를 공식 조회 실패로 기록하지 않는다.

## 산출물

- 176건 범위 manifest
- 176건 KOSIS 검색 명세 JSONL
- 공식 검색 투입 Registry JSONL
- 실제 통합 파이프라인 결과 JSONL과 coverage report
- Claim별 전 단계 결과를 포함한 176행 CSV 평가 원장
- 단계별 전체·검증집합별 성능 JSON 및 쉬운 한국어 TXT 보고서

## 완료 조건

- 176건 범위가 중복·누락 없이 고정된다.
- 모든 Claim에 검색 명세 또는 검색 전 중단 사유가 있다.
- 준비 완료 Claim은 실제 v3 공식 엔진으로 실행된다.
- 공식 API 호출 수와 단계별 결과가 보존된다.
- 평가 원장의 각 단계 합계가 176건과 일치한다.
- Streamlit·배치·CLI가 사용하는 기존 Core Engine을 우회하지 않는다.
