"""Claim interpretation contract."""

from typing import Literal

from pydantic import BaseModel, ConfigDict


CLAIM_DEFINITION = (
    "CLAFACT-AUTO Claim은 뉴스 기사에 포함된 수치적 사실 주장 중, 하나의 통계지표를 "
    "대상으로 특정 시점·지역·모집단·세부 분류 등의 적용 범위와 주장값·단위·비교 "
    "기준·계산 의미를 구조화할 수 있으며, 원문 문장과 기사 기준일에 연결된 고유 "
    "정체성을 보존하고, 하나 이상의 KOSIS 공식 Evidence Cell과 하나의 결정론적 계산을 "
    "통해 하나의 최종 판정을 받을 수 있는 최소 검증 단위다. 하나의 계산과 판정으로 "
    "검증할 수 없는 서로 다른 지표·시점·지역·비교 기준·주장값은 별도 Claim으로 "
    "분리하고, 필수 정보나 공식 근거가 부족하면 임의로 확정하지 않고 사유가 명시된 "
    "HOLD로 보존한다."
)


class ClaimSchema(BaseModel):
    """CLAFACT-AUTO Claim은 뉴스 기사에 포함된 수치적 사실 주장 중, 하나의 통계지표를 대상으로 특정 시점·지역·모집단·세부 분류 등의 적용 범위와 주장값·단위·비교 기준·계산 의미를 구조화할 수 있으며, 원문 문장과 기사 기준일에 연결된 고유 정체성을 보존하고, 하나 이상의 KOSIS 공식 Evidence Cell과 하나의 결정론적 계산을 통해 하나의 최종 판정을 받을 수 있는 최소 검증 단위다. 하나의 계산과 판정으로 검증할 수 없는 서로 다른 지표·시점·지역·비교 기준·주장값은 별도 Claim으로 분리하고, 필수 정보나 공식 근거가 부족하면 임의로 확정하지 않고 사유가 명시된 HOLD로 보존한다."""

    model_config = ConfigDict(extra="forbid")

    claim_id: str
    source_sentence: str
    indicator: str | None = None
    value: float | None = None
    unit: str | None = None
    time: str | None = None
    frequency: str | None = None
    region: str | None = None
    population: str | None = None
    dimension: dict[str, str] | None = None
    comparison: dict[str, str] | None = None
    calculation: str | None = None
    condition: dict[str, str] | None = None
    source_hint: str | None = None
    parse_status: Literal["AUTO_OK", "HOLD", "HUMAN_REVIEW"]
    parse_reason: str | None = None
