# Live KOSIS production path

## Goal

신규 뉴스 Claim은 사전 저장된 판정이나 값 Snapshot의 존재 여부와 무관하게,
유효한 KOSIS API 키로 공식 통계표·메타데이터·값을 조회해 판정한다.

## Production data flow

```text
12 Slot Claim
→ Semantic Standard Mapping
→ KOSIS live Catalog Search
→ KOSIS live ITM/PRD metadata hydration
→ Hard Guard
→ Exact Concept code matching
→ Evidence coordinate resolution
→ KOSIS Parameter API range fetch
→ Python calculation
→ Verdict
```

공식 숫자는 live Parameter API 응답만 사용한다. 과거 기사시점 검증에 필요한
공표일은 official-release-verified 메타데이터만 사용하며 저장 숫자는 읽지 않는다.

## Failure contract

- 모든 Catalog 요청이 실패하면 `KOSIS_CATALOG_UNAVAILABLE`로 기록한다.
- 정상 검색 결과가 없으면 후보 없음 HOLD로 기록한다.
- 공식 Concept 코드와 일치하는 metadata 후보가 없으면 다른 표로 fallback하지 않는다.
- 메타데이터 또는 값 API 실패를 Evidence 후보 없음으로 위장하지 않는다.

## Acceptance case
배추 물가 Claim은 `DT_1J22112`, `A02A01701`, `T10` 좌표를 live로 확정한다.
`202510=136.62`, `202410=208.57`을 한 범위 요청으로 직접 조회한다.
Python 성장률 `-34.49681162199741`로 AUTO MATCH를 반환하고 API hash를
보존한다.
