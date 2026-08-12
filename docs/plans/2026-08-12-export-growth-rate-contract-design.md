# Export Growth Rate Contract Design

## Goal

수출액 GROWTH_RATE Claim이 KOSIS 검색 전에 검증 가능한 12슬롯을 갖추도록 하고, 분기 전년 대비·전분기 대비 공식값 계산까지 동일 동적 엔진에서 처리한다.

## Considered approaches

1. 현재 8건만 HOLD 규칙으로 분리: 빠르지만 신규 정상 분기 성장률을 AUTO 처리하지 못한다.
2. 슬롯 계약과 분기 계산 지원을 함께 구현: 잘못된 Claim은 앞단 HOLD, 완전한 Claim은 두 Evidence Cell과 Python 계산으로 진행한다. 이 방식을 선택한다.
3. LLM이 누락 슬롯과 비교기간을 임의 보정: 자동화율은 높아 보이지만 공식 근거 좌표를 잘못 선택할 위험이 있어 배제한다.

## Contract

- calculation은 GROWTH_RATE이고 unit은 % 또는 호환 백분율이어야 한다.
- comparison.type은 YEAR_OVER_YEAR, MONTH_OVER_MONTH, QUARTER_OVER_QUARTER 중 하나여야 한다.
- condition.direction은 INCREASE 또는 DECREASE여야 한다.
- 여러 성장률 대상이 한 문장에 있으면 단일 target dimension/population으로 분리되어야 한다.
- 원문에 명시된 품목 한정자는 dimension에 보존되어야 한다.
- 분기 기간 YYYY-Qn은 YEAR_OVER_YEAR이면 전년 같은 분기, QUARTER_OVER_QUARTER이면 직전 분기로 해석한다.
- 공식값은 KOSIS에서 현재·비교 두 Evidence Cell을 조회하고 Python GROWTH_RATE 함수가 계산한다.

## Current 8-record disposition

- 잘못 선택된 성장률 값 1건
- comparison.type 누락 5건
- 품목 dimension 누락 1건
- 다중 성장률 target 미분리 1건

현재 8건은 모두 CLAIM_PARSE_UNCERTAIN이 정상 결과다. 향후 완전한 신규 Claim은 동일 계약을 통과해 동적 KOSIS 계산으로 진행한다.