from datetime import date

from core.dynamic_kosis_verifier import verify_claim_against_kosis
from core.kosis_fetcher import KosisValue
from schemas.candidate import KosisCandidateSchema
from schemas.claim import ClaimSchema
from schemas.concept import StandardConceptSchema


class FixedOfficialFetcher:
    def fetch(self, cell, *, article_date):
        assert cell.tbl_id == "DT_1DA7028S"
        assert cell.dimension_codes == {"B": "0", "J": "00"}
        assert article_date == date(2025, 1, 15)
        return KosisValue(28041.0, "SUCCESS", "test", "API")


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
