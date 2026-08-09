# CPI 등록 경로 추적 및 Function Calling 연결 설계

## 목표

등록된 CPI 품목의 성장률 검증 결과가 일반 파이프라인과 동일한 내부 계약을 제공하도록 정합화한다. 명시된 비교 기준을 12슬롯에 보존하고, 실제로 실행한 단계만 추적하며, Streamlit에서 HCX Structured Output과 제한된 `emit_claim` Function Calling을 설정으로 선택할 수 있게 한다.

## 선택한 접근

등록 CPI 경로는 일반 fuzzy 검색으로 되돌리지 않는다. 승인된 `cpi_detail_growth_profiles.json` 좌표를 사용하는 현재 안전 경계를 유지하면서, 등록 프로필에서 표준 Concept와 표시용 Candidate를 함께 만든다. 이 방식은 공식 좌표를 LLM이 선택하지 않는다는 원칙과 Hard Guard 우선 순서를 유지한다.

비교 기준은 HCX 프롬프트만 신뢰하지 않고, 명시적인 한국어 표현인 `전년 동월 대비`를 파싱 후 결정론적으로 보완한다. 원문에 없는 비교 정보는 생성하지 않는다.

등록 프로필 경로에서는 일반 `SEMANTIC_MAPPING`과 `CATALOG_SEARCH`를 실행하지 않으므로 두 단계를 `SKIPPED`로 기록한다. 대신 등록 프로필 조회 결과를 `HARD_GUARD=PASS`, `SEMANTIC_MATCH=PASS`의 `output_ref`로 남긴다.

Function Calling은 `CLAFACT_HCX_EXTRACTION_MODE=function_calling`일 때만 활성화한다. 기본값은 기존 `structured_output`으로 유지하며, 두 모드 모두 동일한 `ClaimOutputPayload` 검증을 통과해야 한다. 어떤 모드에서도 KOSIS 조회·좌표 선택·계산·판정 함수를 LLM 도구로 노출하지 않는다.

## 오류 처리

지원하지 않는 추출 모드는 설정 단계에서 명시적 오류로 차단한다. Function Calling 응답은 정확히 하나의 `emit_claim` 호출만 허용하고 기존 엄격 스키마로 검증한다. 등록 CPI 프로필을 찾지 못하면 기존 일반 의미매핑·카탈로그 경로로 진행한다.

## 테스트

- 명시적 전년 동월 비교의 결정론적 보완
- 등록 CPI 프로필의 표준 Concept 및 Candidate 생성
- 등록 경로에서 일반 의미매핑·카탈로그가 `SKIPPED`로 기록되는지 검증
- 설정값에 따른 HCX extractor 선택 및 잘못된 설정 차단
- 기존 CPI 공식값 계산과 MATCH 판정 회귀 검증

