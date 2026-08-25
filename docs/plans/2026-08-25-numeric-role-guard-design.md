# 숫자 역할 검증 설계

## 목표

LLM이 연령·시점·기간 표현을 기사 통계값으로 잘못 선택해도 KOSIS 조회 전에 Core 파이프라인이 이를 차단한다. Streamlit, 배치, CLI는 모두 같은 Core 검증 결과를 사용한다.

## 선택한 방식

프롬프트만 수정하지 않고 결정론적 숫자 역할 검증기를 추가한다. 검증기는 Claim의 `value`와 `unit`이 원문에서 어떤 역할로 쓰였는지 확인한다.

- `20대 인구`, `80대 사망자`: 연령 집단이므로 기사값으로 사용할 수 없다.
- `5개월 연속`: 기간이므로 `5개`라는 기사값으로 사용할 수 없다.
- `자동차 100대 판매`: 통계 수량이므로 정상 기사값으로 허용한다.

역할 충돌 시 Claim을 `HOLD`로 바꾸고 `TARGET_NUMERIC_ROLE_CONFLICT:<ROLE>`을 기록한다. 자동으로 다른 숫자를 추측하지 않는다.

## 적용 경로

1. 신규 기사: `parse_claim`에서 LLM Structured Output 직후 검증한다.
2. 저장 Claim 재실행: `recover_validated_claim`에서 `AUTO_OK`를 포함해 다시 검증한다.
3. Streamlit: 기존 `verify_dashboard_article -> CanonicalPipeline -> unified_claim_pipeline` 경로를 그대로 사용하므로 별도 UI 분기를 만들지 않는다.

## 완료 조건

- 연령·기간 오선택 회귀 테스트가 수정 전 실패하고 수정 후 통과한다.
- 정상 차량 수량은 계속 통과한다.
- 대시보드 공통 경로에서 잘못된 Claim은 공식 조회 서비스까지 도달하지 않는다.
- 관련 테스트와 전체 테스트에서 기존 기준선 8개 외의 새로운 실패가 없다.
