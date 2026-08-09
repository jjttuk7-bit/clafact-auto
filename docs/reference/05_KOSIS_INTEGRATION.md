# CLAFACT-AUTO KOSIS Integration

## 현재 자산

KOSIS 후보 통계표 350개 Metadata.

주요 필드:
- ORG_ID / ORG_NM
- TBL_ID / TBL_NM
- CORE_ITEM_IDS / CORE_ITEM_NAMES
- DIMENSION_IDS / DIMENSION_NAMES
- DIMENSION_MEMBERS_JSON
- UNIT_NAMES
- PRD
- SOURCE_STAT_ID / SOURCE_JOSA_NM
- METADATA_STATUS

## 원칙

```text
사전:
Metadata Collector
→ Catalog 구축
→ Index 저장

실시간:
Claim
→ Catalog 검색
→ Evidence Cell
→ 필요한 실제 값만 KOSIS API 조회
```

매 Claim마다 Metadata Collector를 다시 실행하지 않는다.

## API 상태

- SUCCESS
- NO_DATA
- TIMEOUT
- CONNECTION_RESET
- INVALID_RESPONSE
- RATE_LIMIT

API 실패:
`FETCH_ERROR → HOLD`

## Snapshot

저장 권장:
- request_params
- response_value
- retrieved_at
- response_hash
- source_url

## Evidence Cell Canonical Key

```text
ORG={ORG_ID}|TBL={TBL_ID}|ITM={ITM_ID}|OBJ={OBJ_ID}|MEMBER={MEMBER}|PRD_SE={PRD_SE}|PRD_DE={PRD_DE}
```
