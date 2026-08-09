# CLAFACT-AUTO Product Requirements

## 제품 정의

뉴스 기사 또는 문장을 입력받아 수치 Claim을 구조화하고,
KOSIS 공식통계와 비교해 MATCH / MISMATCH / UNDETERMINED를 판정하는 자동 검증 엔진.

## MVP 범위

포함:
- 직접값
- 차이
- 증감률
- 비율/비중
- 배수
- 순위
- 임계값

우선 제외:
- 여러 문장에 걸친 복합 Claim
- KOSIS 외 민간데이터
- 실시간 시세
- 전망/예측치의 자동 확정 판정

## 입력

- 단일 뉴스 문장
- 기사 본문
- CSV

## 출력

```text
원문 Claim
12 Semantic Slots
Standard Concept
KOSIS Match Candidate
Hard Guard 결과
Semantic Score
Evidence Cell
KOSIS 공식값
Calculation
Verdict
Reason
Status
```

## 목표 응답시간

- 직접값: 2~5초
- 일반 계산: 5~10초
- 복수 셀/순위: 최대 15초 내외

## 라우팅 상태

- AUTO_MATCH
- HOLD
- HUMAN_REVIEW
- UNDETERMINED

## MVP 성공 조건

1. 골든셋 20~30건 E2E 실행
2. Claim → Evidence → Verdict 경로 로그 저장
3. 잘못된 후보 강제 선택 금지
4. KOSIS 공식값은 API/Snapshot에서만 사용
5. 계산 재현 가능
6. 한 건 직접값 Claim 5~10초 내 처리
