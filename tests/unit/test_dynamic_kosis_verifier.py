from datetime import date

import pytest

from core.dynamic_kosis_verifier import verify_claim_against_kosis
from core.kosis_fetcher import KosisValue
from core.kosis_publication import PublicationEvidence
from schemas.candidate import KosisCandidateSchema
from schemas.claim import ClaimSchema
from schemas.concept import StandardConceptSchema


class FixedOfficialFetcher:
    def fetch(self, cell, *, article_date):
        assert cell.tbl_id == "DT_1DA7028S"
        assert cell.dimension_codes == {"B": "0", "J": "00"}
        assert article_date == date(2025, 1, 15)
        return KosisValue(
            28041.0, "SUCCESS", "test", "API",
            PublicationEvidence(
                status="VERIFIED", published_at=date(2025, 1, 15),
                pub_period="월", pub_date_text="2025-01-15",
                publication_method_url="https://kostat.go.kr/release",
                source_url="https://kosis.kr/openapi/statisticsExplData.do",
                retrieved_at="2025-01-15T00:00:00Z", content_hash="c" * 64,
            ),
        )


def test_employment_claim_is_auto_verified_with_dynamic_kosis_coordinate() -> None:
    claim = ClaimSchema(
        claim_id="employment-202412",
        source_sentence="2024년 12월 취업자 수는 2,804만1천 명이었다.",
        indicator="취업자 수",
        value=28_041_000,
        unit="명",
        time="2024년 12월",
        frequency="월",
        region="한국",
        parse_status="AUTO_OK",
    )
    concept = StandardConceptSchema(
        concept_id="employment_count",
        canonical_name="취업자 수",
        standard_key="employment_count",
        matched_alias="취업자 수",
        status="MATCHED",
    )
    candidate = KosisCandidateSchema(
        org_id="101",
        tbl_id="DT_1DA7028S",
        tbl_name="성/종사상지위별 취업자",
        core_item_ids=["T30"],
        core_item_names=["취업자"],
        dimension_ids=["B", "J"],
        dimension_names=["성별", "종사상지위"],
        dimension_members={"B": ["계", "남자", "여자"], "J": ["계", "상용근로자"]},
        dimension_member_codes={"B": {"계": "0", "남자": "1", "여자": "2"}, "J": {"계": "00", "상용근로자": "10"}},
        unit_names=["천명"],
        frequency="월",
        metadata_status="OFFICIAL_METADATA_READY",
    )

    verdict = verify_claim_against_kosis(
        claim,
        concept,
        [candidate],
        article_date=date(2025, 1, 15),
        official_fetcher=FixedOfficialFetcher(),
    )

    assert verdict.route_status == "AUTO"
    assert verdict.verdict == "MATCH"
    assert verdict.calculated_value == 28_041_000
    assert verdict.evidence_cells[0].dimension_codes == {"B": "0", "J": "00"}
    publication = verdict.official_value_provenance[0].publication
    assert publication is not None
    assert publication.published_at == date(2025, 1, 15)
    assert publication.source_url == "https://kosis.kr/openapi/statisticsExplData.do"
    assert publication.content_hash == "c" * 64


class RoundedEmploymentOfficialFetcher:
    def fetch(self, cell, *, article_date):
        return KosisValue(28041.1, "SUCCESS", "test", "API")


def test_korean_thousand_persons_claim_accepts_official_sub_thousand_rounding() -> None:
    claim = ClaimSchema(
        claim_id="employment-rounded", source_sentence="2024년 12월 취업자 수는 2,804만1천 명이었다.",
        indicator="취업자 수", value=28_041_000, unit="명", time="2024년 12월",
        frequency="월", region="한국", parse_status="AUTO_OK",
    )
    concept = StandardConceptSchema(
        concept_id="employment_count", canonical_name="취업자 수", standard_key="employment_count",
        matched_alias="취업자 수", status="MATCHED",
    )
    candidate = KosisCandidateSchema(
        org_id="101", tbl_id="DT_1DA7028S", tbl_name="성/종사상지위별 취업자",
        core_item_ids=["T30"], core_item_names=["취업자"], dimension_ids=["B", "J"],
        dimension_names=["성별", "종사상지위"], dimension_members={"B": ["계"], "J": ["계"]},
        dimension_member_codes={"B": {"계": "0"}, "J": {"계": "00"}},
        unit_names=["천명"], frequency="월", metadata_status="OFFICIAL_METADATA_READY",
    )

    verdict = verify_claim_against_kosis(
        claim, concept, [candidate], article_date=date(2025, 1, 15), official_fetcher=RoundedEmploymentOfficialFetcher()
    )

    assert verdict.route_status == "AUTO"
    assert verdict.verdict == "MATCH"

def test_unresolved_candidate_does_not_block_confirmed_coordinate() -> None:
    claim = ClaimSchema(
        claim_id="employment-fallback",
        source_sentence="2024년 12월 취업자 수는 2,804만1천 명이었다.",
        indicator="취업자 수", value=28_041_000, unit="명", time="2024년 12월",
        frequency="월", region="한국", parse_status="AUTO_OK",
    )
    concept = StandardConceptSchema(
        concept_id="employment_count", canonical_name="취업자 수", standard_key="employment_count",
        matched_alias="취업자 수", status="MATCHED",
    )
    unresolved = KosisCandidateSchema(
        org_id="101", tbl_id="DT_UNRESOLVED", tbl_name="취업자", core_item_ids=["T30"],
        core_item_names=["취업자"], dimension_ids=["B"], dimension_names=["성별"],
        dimension_members={"B": ["계"]}, unit_names=["천명"], frequency="월",
        metadata_status="OFFICIAL_METADATA_READY",
    )
    confirmed = KosisCandidateSchema(
        org_id="101", tbl_id="DT_1DA7028S", tbl_name="성/종사상지위별 취업자", core_item_ids=["T30"],
        core_item_names=["취업자"], dimension_ids=["B", "J"], dimension_names=["성별", "종사상지위"],
        dimension_members={"B": ["계"], "J": ["계"]},
        dimension_member_codes={"B": {"계": "0"}, "J": {"계": "00"}},
        unit_names=["천명"], frequency="월", metadata_status="OFFICIAL_METADATA_READY",
    )

    verdict = verify_claim_against_kosis(
        claim, concept, [unresolved, confirmed], article_date=date(2025, 1, 15), official_fetcher=FixedOfficialFetcher()
    )

    assert verdict.route_status == "AUTO"
    assert verdict.evidence_cells[0].tbl_id == "DT_1DA7028S"

def test_hard_guard_runs_before_coordinate_resolution_and_value_fetch() -> None:
    claim = ClaimSchema(
        claim_id="employment-frequency-conflict", source_sentence="2024년 취업자 수는 2,804만 명이었다.",
        indicator="취업자 수", value=28_040_000, unit="명", time="2024년",
        frequency="년", region="한국", parse_status="AUTO_OK",
    )
    concept = StandardConceptSchema(
        concept_id="employment_count", canonical_name="취업자 수", standard_key="employment_count",
        matched_alias="취업자 수", status="MATCHED",
    )
    monthly_candidate = KosisCandidateSchema(
        org_id="101", tbl_id="DT_MONTHLY", tbl_name="월 취업자", core_item_ids=["T30"],
        core_item_names=["취업자"], unit_names=["천명"], frequency="월",
        metadata_status="OFFICIAL_METADATA_READY",
    )

    class Fetcher:
        def fetch(self, *_args, **_kwargs):
            raise AssertionError("Hard Guard rejection must not fetch an official value")

    verdict = verify_claim_against_kosis(
        claim, concept, [monthly_candidate], article_date=date(2025, 1, 15), official_fetcher=Fetcher()
    )

    assert verdict.route_status == "HOLD"
    assert verdict.reason_code == "NO_HARD_GUARD_CANDIDATE"


def test_year_over_year_claim_fetches_two_periods_and_calculates_growth_rate() -> None:
    claim = ClaimSchema(
        claim_id="employment-yoy", source_sentence="2024년 12월 취업자 수는 전년 동월 대비 1.0% 증가했다.",
        indicator="취업자 수", value=1.0, unit="%", time="2024년 12월", frequency="월", region="한국",
        comparison={"type": "YEAR_OVER_YEAR"}, calculation="GROWTH_RATE", parse_status="AUTO_OK",
    )
    concept = StandardConceptSchema(
        concept_id="employment_count", canonical_name="취업자 수", standard_key="employment_count",
        matched_alias="취업자 수", status="MATCHED",
    )
    candidate = KosisCandidateSchema(
        org_id="101", tbl_id="DT_1DA7028S", tbl_name="성/종사상지위별 취업자",
        core_item_ids=["T30"], core_item_names=["취업자"], dimension_ids=["B", "J"],
        dimension_names=["성별", "종사상지위"], dimension_members={"B": ["계"], "J": ["계"]},
        dimension_member_codes={"B": {"계": "0"}, "J": {"계": "00"}},
        unit_names=["천명"], frequency="월", metadata_status="OFFICIAL_METADATA_READY",
    )

    class Fetcher:
        def fetch(self, cell, *, article_date):
            return KosisValue({"2024-12": 101.0, "2023-12": 100.0}[cell.prd_de], "SUCCESS", "test", "API")

    verdict = verify_claim_against_kosis(
        claim, concept, [candidate], article_date=date(2025, 1, 15), official_fetcher=Fetcher()
    )

    assert verdict.route_status == "AUTO"
    assert verdict.verdict == "MATCH"
    assert verdict.calculated_value == 1.0
    assert [cell.prd_de for cell in verdict.evidence_cells] == ["2024-12", "2023-12"]

def test_unresolved_concept_holds_at_semantic_mapping_before_catalog() -> None:
    unresolved = StandardConceptSchema(
        concept_id="UNRESOLVED", canonical_name="UNRESOLVED",
        standard_key="unresolved", status="UNRESOLVED",
    )
    claim = ClaimSchema(
        claim_id="unknown", source_sentence="2025년 10월 미상 물가는 3% 상승했다.",
        indicator="물가", value=3, unit="%", time="2025년 10월",
        calculation="GROWTH_RATE", comparison={"type": "YEAR_OVER_YEAR"}, parse_status="AUTO_OK",
    )
    class Fetcher:
        def fetch(self, *_args, **_kwargs):
            raise AssertionError("Unresolved concepts must not fetch values")

    verdict = verify_claim_against_kosis(
        claim, unresolved, [], article_date=date(2025, 11, 4), official_fetcher=Fetcher()
    )

    assert verdict.reason_code == "CONCEPT_NOT_FOUND"
    assert verdict.execution_trace.events[-1].stage == "SEMANTIC_MAPPING"
    assert verdict.execution_trace.events[-1].status == "HOLD"

def test_official_value_adapter_exception_becomes_fetch_failed_hold() -> None:
    claim = ClaimSchema(
        claim_id="cpi-fetch-failure",
        source_sentence="2025년 10월 배추 물가는 전년 동월 대비 34.5% 하락했다.",
        indicator="물가", value=-34.5, unit="%", time="2025년 10월",
        frequency="월", dimension={"item": "배추"},
        comparison={"type": "YEAR_OVER_YEAR"}, calculation="GROWTH_RATE",
        parse_status="AUTO_OK",
    )
    concept = StandardConceptSchema(
        concept_id="CPI_DETAIL:A02A01701", canonical_name="배추 소비자물가지수",
        standard_key="cpi_detail:A02A01701", status="MATCHED",
    )
    candidate = KosisCandidateSchema(
        org_id="101", tbl_id="DT_1J22112", tbl_name="품목별 소비자물가지수",
        core_item_ids=["T"], core_item_names=["소비자물가지수"],
        dimension_ids=["C", "I"], dimension_names=["지역", "품목별"],
        dimension_members={"C": ["전국"], "I": ["배추"]},
        dimension_member_codes={"C": {"전국": "T10"}, "I": {"배추": "A02A01701"}},
        unit_names=["2020=100"], frequency="월",
        metadata_status="OFFICIAL_METADATA_READY",
    )

    class FailingFetcher:
        def fetch_many(self, _cells, *, article_date):
            raise RuntimeError("transient KOSIS value failure")

    verdict = verify_claim_against_kosis(
        claim, concept, [candidate], article_date=date(2025, 11, 4),
        official_fetcher=FailingFetcher(),
    )

    assert verdict.route_status == "HOLD"
    assert verdict.reason_code == "FETCH_FAILED"


def test_publication_failure_hold_preserves_attempt_provenance() -> None:
    claim = ClaimSchema(
        claim_id="publication-failure", source_sentence="2024년 12월 취업자 수는 2804만1천 명이었다.",
        indicator="취업자 수", value=28_041_000, unit="명", time="2024년 12월",
        frequency="월", region="한국", parse_status="AUTO_OK",
    )
    concept = StandardConceptSchema(
        concept_id="employment_count", canonical_name="취업자 수",
        standard_key="employment_count", status="MATCHED",
    )
    candidate = KosisCandidateSchema(
        org_id="101", tbl_id="DT_1DA7028S", tbl_name="취업자",
        core_item_ids=["T30"], core_item_names=["취업자"],
        dimension_ids=["B"], dimension_names=["성별"], dimension_members={"B": ["계"]},
        dimension_member_codes={"B": {"계": "0"}}, unit_names=["천명"], frequency="월",
        metadata_status="OFFICIAL_METADATA_READY",
    )

    class Fetcher:
        def fetch(self, _cell, *, article_date):
            return KosisValue(
                None, "PUBLICATION_FETCH_FAILED", "value-hash", "API",
                PublicationEvidence(
                    status="FETCH_FAILED", source_url="https://kosis.kr/openapi/statisticsExplData.do",
                    retrieved_at="2025-01-15T00:00:00Z", content_hash="e" * 64,
                ),
            )

    verdict = verify_claim_against_kosis(
        claim, concept, [candidate], article_date=date(2025, 1, 15), official_fetcher=Fetcher()
    )

    assert verdict.route_status == "HOLD"
    assert verdict.reason_code == "PUBLICATION_FETCH_FAILED"
    assert len(verdict.official_value_provenance) == 1
    assert verdict.official_value_provenance[0].publication is not None
    assert verdict.official_value_provenance[0].publication.content_hash == "e" * 64
def test_direct_value_tie_is_resolved_only_when_official_values_and_publication_dates_match() -> None:
    claim = ClaimSchema(
        claim_id="employment-tie", source_sentence="2024년 12월 취업자 수는 2804만1000명이었다.",
        indicator="취업자 수", value=28_041_000, unit="명", time="2024년 12월",
        frequency="월", region="한국", calculation="DIRECT_VALUE", parse_status="AUTO_OK",
    )
    concept = StandardConceptSchema(
        concept_id="employment_count", canonical_name="취업자 수", standard_key="employment_count",
        matched_alias="취업자 수", status="MATCHED",
    )
    candidates = [
        KosisCandidateSchema(
            org_id="101", tbl_id=table_id, tbl_name="경제활동인구 총괄", core_item_ids=["T30"],
            core_item_names=["취업자"], dimension_ids=["B"], dimension_names=["성별"],
            dimension_members={"B": ["계"]}, dimension_member_codes={"B": {"계": "0"}},
            unit_names=["천명"], frequency="월", metadata_status="OFFICIAL_METADATA_READY",
        )
        for table_id in ("DT_A", "DT_B")
    ]

    class Fetcher:
        def fetch(self, _cell, *, article_date):
            return KosisValue(
                28041.0, "SUCCESS", "official", "API",
                PublicationEvidence(
                    status="VERIFIED", published_at=date(2025, 1, 15), source_url="https://kostat.go.kr/release",
                    retrieved_at="2025-01-15T00:00:00Z", content_hash="a" * 64,
                ),
            )

    verdict = verify_claim_against_kosis(
        claim, concept, candidates, article_date=date(2025, 1, 15), official_fetcher=Fetcher()
    )

    assert verdict.route_status == "AUTO"
    assert verdict.reason_code == "WITHIN_TOLERANCE"
    assert verdict.verdict == "MATCH"

def test_direct_value_tie_with_different_official_values_remains_hold() -> None:
    claim = ClaimSchema(
        claim_id="employment-unequal-tie", source_sentence="2024년 12월 취업자 수는 2804만1000명이었다.",
        indicator="취업자 수", value=28_041_000, unit="명", time="2024년 12월",
        frequency="월", region="한국", calculation="DIRECT_VALUE", parse_status="AUTO_OK",
    )
    concept = StandardConceptSchema(
        concept_id="employment_count", canonical_name="취업자 수", standard_key="employment_count",
        matched_alias="취업자 수", status="MATCHED",
    )
    candidates = [
        KosisCandidateSchema(
            org_id="101", tbl_id=table_id, tbl_name="경제활동인구 총괄", core_item_ids=["T30"],
            core_item_names=["취업자"], dimension_ids=["B"], dimension_names=["성별"],
            dimension_members={"B": ["계"]}, dimension_member_codes={"B": {"계": "0"}},
            unit_names=["천명"], frequency="월", metadata_status="OFFICIAL_METADATA_READY",
        )
        for table_id in ("DT_A", "DT_B")
    ]

    class Fetcher:
        def fetch(self, cell, *, article_date):
            value = 28041.0 if cell.tbl_id == "DT_A" else 28042.0
            return KosisValue(
                value, "SUCCESS", "official", "API",
                PublicationEvidence(status="VERIFIED", published_at=date(2025, 1, 15)),
            )

    verdict = verify_claim_against_kosis(
        claim, concept, candidates, article_date=date(2025, 1, 15), official_fetcher=Fetcher()
    )

    assert verdict.route_status == "HOLD"
    assert verdict.reason_code == "AMBIGUOUS_MARGIN"

@pytest.mark.parametrize("second_current", [4376.3, 4377.3])
def test_difference_tie_requires_equal_two_period_official_evidence(
    second_current: float,
) -> None:
    claim = ClaimSchema(
        claim_id="employment-change-tie",
        source_sentence="임시근로자는 전년 같은 달보다 1만9000명 감소했다.",
        indicator="취업자 수", value=19000, unit="명", time="2024년 12월",
        frequency="월", region="한국", dimension={"고용형태": "임시직"},
        comparison={"type": "YEAR_OVER_YEAR", "operand_source": "OFFICIAL_EVIDENCE"},
        calculation="DIFFERENCE", condition={"direction": "DECREASE"}, parse_status="AUTO_OK",
    )
    concept = StandardConceptSchema(
        concept_id="employment_count", canonical_name="취업자 수",
        standard_key="employment_count", matched_alias="취업자 수", status="MATCHED",
    )
    candidates = [
        KosisCandidateSchema(
            org_id="101", tbl_id=table_id, tbl_name="종사상지위별 취업자",
            core_item_ids=["T30"], core_item_names=["취업자"],
            dimension_ids=["J"], dimension_names=["종사상지위별"],
            dimension_members={"J": ["계", "-임시근로자"]},
            dimension_member_codes={"J": {"계": "00", "-임시근로자": "51"}},
            unit_names=["천명"], frequency="월", metadata_status="OFFICIAL_METADATA_READY",
        )
        for table_id in ("DT_A", "DT_B")
    ]

    class Fetcher:
        def fetch(self, cell, *, article_date):
            current = 4376.3 if cell.tbl_id == "DT_A" else second_current
            value = current if cell.prd_de == "2024-12" else 4395.3
            return KosisValue(
                value, "SUCCESS", "official", "API",
                PublicationEvidence(
                    status="VERIFIED",
                    published_at=date(2025, 1, 15) if cell.prd_de == "2024-12" else date(2024, 1, 15),
                ),
            )

    verdict = verify_claim_against_kosis(
        claim, concept, candidates, article_date=date(2025, 1, 16), official_fetcher=Fetcher(),
    )

    if second_current == 4376.3:
        assert verdict.route_status == "AUTO"
        assert verdict.verdict == "MATCH"
        assert len(verdict.evidence_cells) == 2
    else:
        assert verdict.route_status == "HOLD"
        assert verdict.reason_code == "AMBIGUOUS_MARGIN"
