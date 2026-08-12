# 국가별 수출 직접값 동적 KOSIS 검증 설계

## 목표

`NO_HARD_GUARD_CANDIDATE`의 최상위 지표인 수출액 62건 중 구조적으로 완전한 국가별 직접값 Claim을 KOSIS 공식 국가 차원과 연결한다. 첫 고정 사례는 `A00312_4`의 2024년 대미 수출액이다.

## 범위

- `dimension.raw`에 저장된 JSON 문자열에서 실제 차원 멤버를 안전하게 추출한다.
- Hard Guard와 Evidence Resolver가 동일한 정규화 결과를 사용한다.
- `달러`와 `천달러/천불`을 결정론적으로 변환한다.
- Semantic Standard 검색어로 `국가별 수출액 수입액`을 추가한다.
- 공식 표 `DT_1R11006_FRM101`, 항목 `13103103829T1`, 미국 코드 `13102103829E.US`를 Snapshot으로 검증한다.

## 비범위

RANK, THRESHOLD, DIFFERENCE, `%p`, 차량 대수, 다중 품목·다중 숫자 Claim은 강제로 이 표에 연결하지 않는다. 이들은 별도 구조화/HOLD 분류 대상이다.

## 안전성

KOSIS 최종 셀의 `LST_CHN_DE`가 기사일 뒤라면 값이 일치하더라도 `AS_OF_UNAVAILABLE`을 유지한다. LLM은 공식값이나 계산값을 생성하지 않는다.