from datetime import date

from core.dynamic_kosis_verifier import verify_claim_against_kosis
from core.evidence_resolver import resolve_evidence_cell
from core.kosis_fetcher import KosisValue
from core.semantic_matcher import semantic_match
from schemas.candidate import KosisCandidateSchema
from schemas.claim import ClaimSchema
from schemas.concept import StandardConceptSchema


def _claim() -> ClaimSchema:
    return ClaimSchema(
        claim_id="cpi-processed-food",
        source_sentence="2025년 3월 가공식품 물가는 전년 대비 3.1% 올랐다.",
        indicator="가공식품 물가",
        value=3.1,
        unit="%",
        time="2025년 3월",
        frequency="월",
        region="한국",
        dimension={"품목": "가공식품"},
        comparison={"기준": "전년 대비", "방향": "상승"},
        calculation="GROWTH_RATE",
        parse_status="AUTO_OK",
    )


def _candidate() -> KosisCandidateSchema:
    return KosisCandidateSchema(
        org_id="101", tbl_id="DT_1J22112",
        tbl_name="품목별 소비자물가지수(품목성질별: 2020=100)",
        core_item_ids=["T"], core_item_names=["소비자물가지수"],
        dimension_ids=["C", "I"], dimension_names=["시도별", "품목별"],
        dimension_members={
            "C": ["전국", "서울특별시"],
            "I": ["총지수", "가공식품", "밀가루"],
        },
        dimension_member_codes={
            "C": {"전국": "T10", "서울특별시": "T11"},
            "I": {"총지수": "0", "가공식품": "B01", "밀가루": "B01A01101"},
        },
        unit_names=["2020=100"], frequency="월|분기|년",
        start_period="1975.01", end_period="2026.07",
        metadata_status="OFFICIAL_METADATA_READY",
    )


def test_cpi_dimension_member_resolves_single_official_measurement_item() -> None:
    cell = resolve_evidence_cell(_claim(), _candidate())

    assert cell.status == "CONFIRMED"
    assert cell.itm_id == "T"
    assert cell.dimension_members == {"C": "전국", "I": "가공식품"}
    assert cell.dimension_codes == {"C": "T10", "I": "B01"}
    assert cell.prd_se == "월"
    assert cell.prd_de == "2025-03"


def test_cpi_dimension_member_contributes_to_semantic_match() -> None:
    result = semantic_match(_claim(), [_candidate()])[0]

    assert result.route_status == "AUTO"
    assert result.reason_code == "MATCH_ACCEPTED"


def test_korean_year_over_year_claim_fetches_two_official_periods_and_verdict() -> None:
    periods: list[str] = []

    class Fetcher:
        def fetch(self, cell, *, article_date):
            assert article_date == date(2025, 4, 5)
            periods.append(cell.prd_de)
            return KosisValue({"2025-03": 103.1, "2024-03": 100.0}[cell.prd_de], "SUCCESS", "test", "API")

    concept = StandardConceptSchema(
        concept_id="C000026", canonical_name="물가상승률",
        standard_key="inflation_rate", matched_alias="가공식품 물가",
        status="MATCHED",
    )
    verdict = verify_claim_against_kosis(
        _claim(), concept, [_candidate()],
        article_date=date(2025, 4, 5), official_fetcher=Fetcher(),
    )

    assert periods == ["2025-03", "2024-03"]
    assert verdict.route_status == "AUTO"
    assert verdict.verdict == "MATCH"
    assert verdict.calculated_value is not None
    assert abs(verdict.calculated_value - 3.1) < 1e-9

import pytest


@pytest.mark.parametrize(
    ("comparison_type", "expected_period"),
    [
        ("YEAR_OVER_YEAR", "2024-Q1"),
        ("QUARTER_OVER_QUARTER", "2024-Q4"),
    ],
)
def test_quarterly_growth_claim_fetches_correct_comparison_period(
    comparison_type: str, expected_period: str,
) -> None:
    periods: list[str] = []

    class Fetcher:
        def fetch(self, cell, *, article_date):
            periods.append(cell.prd_de)
            values = {"2025-Q1": 110.0, expected_period: 100.0}
            return KosisValue(values[cell.prd_de], "SUCCESS", "test", "API")

    claim = _claim().model_copy(update={
        "claim_id": f"quarter-{comparison_type}",
        "source_sentence": "2025년 1분기 가공식품 물가는 비교 기간보다 10% 올랐다.",
        "value": 10.0,
        "time": "2025-Q1",
        "frequency": "분기",
        "comparison": {"type": comparison_type},
    })
    concept = StandardConceptSchema(
        concept_id="C000026", canonical_name="물가상승률",
        standard_key="inflation_rate", matched_alias="가공식품 물가",
        status="MATCHED",
    )

    verdict = verify_claim_against_kosis(
        claim, concept, [_candidate()],
        article_date=date(2025, 4, 5), official_fetcher=Fetcher(),
    )

    assert periods == ["2025-Q1", expected_period]
    assert verdict.route_status == "AUTO"
    assert verdict.verdict == "MATCH"

def test_percentage_point_difference_fetches_two_official_periods_and_matches_decrease() -> None:
    periods: list[str] = []

    class Fetcher:
        def fetch(self, cell, *, article_date):
            periods.append(cell.prd_de)
            return KosisValue({"2025": 19.8, "2024": 20.4}[cell.prd_de], "SUCCESS", "test", "API")

    claim = ClaimSchema(
        claim_id="export-share-difference",
        source_sentence="수출 비중은 19.8%로 전년보다 0.6%포인트 줄었다.",
        indicator="수출액",
        value=0.6,
        unit="%p",
        time="2025",
        frequency="년",
        comparison={
            "type": "YEAR_OVER_YEAR",
            "current_value": "19.8",
            "reference_value": "20.4",
            "operand_unit": "%",
        },
        calculation="DIFFERENCE",
        condition={"direction": "DECREASE"},
        parse_status="AUTO_OK",
    )
    candidate = KosisCandidateSchema(
        org_id="134", tbl_id="DT_EXPORT_SHARE", tbl_name="수출 비중",
        core_item_ids=["T"], core_item_names=["수출액"],
        dimension_ids=[], dimension_names=[], dimension_members={},
        dimension_member_codes={}, unit_names=["%"], frequency="년",
        start_period="2000", end_period="2025",
        metadata_status="OFFICIAL_METADATA_READY",
    )
    concept = StandardConceptSchema(
        concept_id="export_value", canonical_name="수출액",
        standard_key="export_value", matched_alias="수출액", status="MATCHED",
    )

    verdict = verify_claim_against_kosis(
        claim, concept, [candidate],
        article_date=date(2026, 1, 1), official_fetcher=Fetcher(),
    )

    assert periods == ["2025", "2024"]
    assert verdict.route_status == "AUTO"
    assert verdict.verdict == "MATCH"
    assert verdict.claim_value == 0.6
    assert abs((verdict.calculated_value or 0) - 0.6) < 1e-9