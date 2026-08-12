# Export Difference Contract Design

## Goal

수출액 DIFFERENCE Claim을 명시적인 현재값·기준값 계약으로 검증하고, KOSIS의 두 공식 Evidence Cell을 Python 차이 계산으로 판정한다.

## Alternatives

1. 현재 A00904_8만 파싱 HOLD로 분리한다. NO_HARD는 없어지지만 신규 DIFFERENCE Claim은 검증할 수 없다.
2. 명시적 피연산자 계약과 동적 두 셀 계산을 구현한다. 안전성과 신규 Claim 지원을 함께 얻으므로 선택한다.
3. 누락된 피연산자를 LLM이 산술 추정한다. 공식 근거와 기사 내 여러 수치가 섞일 위험 때문에 배제한다.

## Slot contract

- calculation은 DIFFERENCE다.
- comparison.type은 YEAR_OVER_YEAR, MONTH_OVER_MONTH, QUARTER_OVER_QUARTER 중 하나다.
- comparison.current_value와 comparison.reference_value는 수치 문자열이다.
- comparison.operand_unit은 두 피연산자의 공통 단위다.
- condition.direction은 INCREASE 또는 DECREASE다.
- abs(current-reference)는 claim.value와 일치해야 하고 부호는 direction과 일치해야 한다.
- 백분율 값의 차이는 claim.unit `%p`, operand_unit `%` 조합을 허용한다.

## Data flow

완전한 Claim은 Semantic Mapping과 Guard를 통과한 뒤 현재 기간과 비교 기간의 동일 KOSIS 좌표 두 개를 만든다. KOSIS 공식값 두 개를 조회하고 Python `current-reference`를 계산한다. 기사값이 양의 변화 폭으로 표현된 경우 direction과 공식값 부호가 일치할 때 절댓값으로 판정한다.

현재 A00904_8은 0.03%, 19.8%, 0.6%p가 서로 다른 의미로 섞였고 direction도 반대로 저장됐다. 명시적 current/reference가 없으므로 `CLAIM_PARSE_UNCERTAIN`으로 이동한다.