# OpenAI Function Calling Claim Extractor Design

## 목표

CLAFACT-AUTO의 Claim Extraction 경계에 OpenAI Responses API 기반 Strict Function Calling을 추가한다. OpenAI는 뉴스 문장을 12개 Semantic Slot으로 구조화하는 역할만 담당한다. KOSIS 후보 검색, 공식값 조회, Python 계산, 최종 판정은 기존 결정론적 파이프라인이 계속 담당한다.

## 핵심 원칙

- OpenAI에 노출하는 Function은 `emit_claim` 하나뿐이다.
- Function Schema는 `strict: true`와 `additionalProperties: false`를 사용한다.
- 모델이 반환한 Function arguments는 Pydantic으로 다시 검증한다.
- OpenAI는 KOSIS 공식값을 생성하거나 조회하지 않는다.
- OpenAI는 계산 또는 최종 Verdict를 수행하지 않는다.
- 모델이 `HOLD` 또는 `HUMAN_REVIEW`를 반환하면 다른 모델로 재판정하지 않는다.
- HCX fallback은 인증을 제외한 일시적 전송 오류나 응답 계약 오류 등 기술적 실패에만 사용한다.
- API Key는 환경변수와 Streamlit Secrets로만 관리하고 화면이나 로그에 표시하지 않는다.

## Provider 구성

`Settings`에 다음 설정을 추가한다.

- `claim_provider`: `CLAFACT_CLAIM_PROVIDER`, 기본값 `hcx`
- `openai_api_key`: `OPENAI_API_KEY`
- `openai_model`: `CLAFACT_OPENAI_MODEL`, 기본값 `gpt-5.6-luna`

`create_claim_extractor()`는 `claim_provider`에 따라 OpenAI 또는 HCX Adapter를 선택한다. OpenAI가 선택되고 기술적 실패가 발생하면 HCX Key가 있을 때에만 HCX Structured Output Adapter로 fallback한다.

## Strict Tool Contract

Responses API에는 OpenAI 형식의 `emit_claim` Function Tool을 전달하고 호출을 강제한다. 최상위 필드는 기존 `ClaimOutputPayload`와 동일하게 유지한다.

기존 `dimension`, `comparison`, `condition`은 임의 키를 가진 객체이다. OpenAI Strict Schema는 각 객체에 `additionalProperties: false`를 요구하므로 Provider 경계에서는 다음과 같은 key/value entry 배열로 표현한다.

```json
{
  "dimension": [
    {"key": "sex", "value": "여성"}
  ]
}
```

각 entry는 `key`, `value`를 모두 required로 갖고 `additionalProperties: false`를 사용한다. Adapter는 검증을 마친 배열을 내부 `dict[str, str]`로 변환한다. 중복 key는 계약 오류로 처리하며 임의로 덮어쓰지 않는다.

## 요청과 응답 흐름

1. 정규화된 뉴스 문장을 Responses API에 전달한다.
2. `tool_choice`로 `emit_claim` 호출을 강제한다.
3. 응답에서 정확히 한 개의 `emit_claim` Function Call만 허용한다.
4. arguments를 Provider용 Pydantic Schema로 검증한다.
5. entry 배열을 내부 dict 슬롯으로 변환한다.
6. 기존 `ClaimOutputPayload`와 `ClaimSchema`로 다시 검증한다.
7. 이후 Semantic Mapping부터 Verdict까지 기존 파이프라인을 그대로 실행한다.

## 오류 처리

- API Key 누락: 명시적인 설정 오류로 HOLD 처리하며 fallback으로 숨기지 않는다.
- 인증 또는 권한 오류: 설정 오류로 분류하고 fallback하지 않는다.
- timeout, 429, 5xx: 기술적 실패로 분류하여 HCX fallback을 한 번 허용한다.
- Function Call 누락·복수 호출·잘못된 함수명·Schema 불일치: 계약 오류로 분류하여 HCX fallback을 한 번 허용한다.
- OpenAI가 유효한 `HOLD/HUMAN_REVIEW` Claim을 반환: 정상 결과이므로 fallback하지 않는다.
- 두 Provider가 모두 실패: 자유 텍스트를 사용하지 않고 파이프라인을 HOLD로 종료한다.

## Streamlit 표시

운영 연결 상태에는 다음을 표시한다.

- KOSIS API
- 기본 Claim Provider와 연결 여부
- HCX fallback 구성 여부

검증 결과에는 실제 사용된 Provider를 표시하되 API Key나 원문 응답은 표시하지 않는다.

## 테스트 전략

- Settings가 OpenAI 환경변수를 읽는 테스트
- Provider Factory가 OpenAI/HCX를 올바르게 선택하는 테스트
- OpenAI 요청에 `emit_claim`, `strict: true`, 강제 tool choice가 포함되는 테스트
- 정상 Function Call을 12 Slot Claim으로 변환하는 테스트
- null과 빈 배열을 내부 `None`으로 변환하는 테스트
- 중첩 슬롯 entry 배열을 dict로 변환하는 테스트
- 중복 key 거부 테스트
- Function Call 누락·복수 호출·잘못된 함수명 거부 테스트
- 기술적 실패에서만 HCX fallback하는 테스트
- 정상 `HOLD/HUMAN_REVIEW`에는 fallback하지 않는 테스트
- 단문 및 배치 파이프라인 회귀 테스트

## 완료 기준

- `CLAFACT_CLAIM_PROVIDER=openai`에서 OpenAI Strict Function Calling이 사용된다.
- `CLAFACT_OPENAI_MODEL=gpt-5.6-luna`가 요청 모델로 사용된다.
- 12 Slot Claim이 Pydantic 내부 계약으로만 전달된다.
- KOSIS와 Verdict 계층은 LLM Function으로 노출되지 않는다.
- 모든 신규·기존 테스트가 통과한다.
