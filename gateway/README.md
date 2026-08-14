# CLAFACT-AUTO Official KOSIS Gateway

이 서비스는 CLAFACT-AUTO의 동일한 공식 근거 엔진을 실행한다. Streamlit은 Claim의 구조화된 12슬롯과 기사일만 이 Gateway에 보내며, KOSIS API 키는 Gateway 환경변수에만 둔다.

## Render 설정

- Build Command: `pip install -r requirements.txt`
- Start Command: `uvicorn gateway.official_gateway_app:app --host 0.0.0.0 --port $PORT`
- Instance Type: Free (검증용)

환경변수 두 개를 설정한다.

- `KOSIS_API_KEY`: KOSIS에서 발급한 실제 키
- `CLAFACT_GATEWAY_TOKEN`: 임의의 충분히 긴 비밀 문자열

`/verify`는 `X-CLAFACT-GATEWAY-TOKEN` 헤더가 `CLAFACT_GATEWAY_TOKEN`과 일치할 때만 요청을 처리한다. 키·토큰·KOSIS 원문 응답은 결과나 로그에 저장하지 않는다.

## 연결

Render가 발급한 HTTPS 서비스 주소를 Streamlit Cloud에 `CLAFACT_OFFICIAL_GATEWAY_URL`로, 같은 토큰을 `CLAFACT_GATEWAY_TOKEN`으로 등록한다.