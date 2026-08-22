from datetime import date

from core.dynamic_kosis_verifier import verify_claim_against_kosis
from core.kosis_fetcher import KosisValue
from core.kosis_publication import PublicationEvidence
from schemas.candidate import KosisCandidateSchema
from schemas.claim import ClaimSchema
from schemas.concept import StandardConceptSchema


def _claim() -> ClaimSchema:
    return ClaimSchema(
        claim_id="live-provenance",
        source_sentence="2024년 12월 취업자 수는 전년 동월 대비 1% 증가했다.",
        indicator="취업자 수",
        value=1.0,
        unit="%",
        time="2024년 12월",
        frequency="월",
        calculation="GROWTH_RATE",
        comparison={"type": "YEAR_OVER_YEAR"},
        parse_status="AUTO_OK",
    )


def _concept() -> StandardConceptSchema:
    return StandardConceptSchema(
        concept_id="employment",
        canonical_name="취업자 수",
        standard_key="employment",
        status="MATCHED",
    )


def _candidate() -> KosisCandidateSchema:
    return KosisCandidateSchema(
        org_id="101",
        tbl_id="DT_EMP",
        tbl_name="취업자 수",
        core_item_ids=["T"],
        core_item_names=["취업자 수"],
        dimension_ids=["C1"],
        dimension_names=["성별"],
        dimension_members={"C1": ["계"]},
        dimension_member_codes={"C1": {"계": "0"}},
        unit_names=["천명"],
        frequency="월",
        metadata_status="OFFICIAL_METADATA_READY",
    )


def test_auto_verdict_preserves_value_url_time_hash_and_publication() -> None:
    class Fetcher:
        def fetch_many(self, cells, *, article_date):
            values = {"2024-12": 101.0, "2023-12": 100.0}
            return [
                KosisValue(
                    values[cell.prd_de],
                    "SUCCESS",
                    "a" * 64,
                    "API",
                    PublicationEvidence(
                        status="VERIFIED",
                        published_at=date(2025, 1, 15),
                        source_url="https://kostat.go.kr/board.es?act=view",
                        retrieved_at="2025-01-15T00:00:00Z",
                        content_hash="b" * 64,
                    ),
                    source_url="https://kosis.kr/openapi/Param/statisticsParameterData.do?orgId=101&tblId=DT_EMP",
                    retrieved_at="2025-01-15T00:00:00Z",
                )
                for cell in cells
            ]

    verdict = verify_claim_against_kosis(
        _claim(),
        _concept(),
        [_candidate()],
        article_date=date(2025, 1, 16),
        official_fetcher=Fetcher(),
    )

    assert verdict.route_status == "AUTO"
    assert len(verdict.official_value_provenance) == 2
    assert all(item.source_url.startswith("https://kosis.kr/openapi/") for item in verdict.official_value_provenance)
    assert all(item.retrieved_at == "2025-01-15T00:00:00Z" for item in verdict.official_value_provenance)
    assert all(item.content_hash == "a" * 64 for item in verdict.official_value_provenance)
    assert all(item.publication is not None for item in verdict.official_value_provenance)


def test_missing_value_response_is_a_named_fetch_hold() -> None:
    class Fetcher:
        def fetch_many(self, _cells, *, article_date):
            return []

    verdict = verify_claim_against_kosis(
        _claim(),
        _concept(),
        [_candidate()],
        article_date=date(2025, 1, 16),
        official_fetcher=Fetcher(),
    )

    assert verdict.route_status == "HOLD"
    assert verdict.reason_code == "FETCH_FAILED"


def test_zero_denominator_is_a_named_calculation_hold() -> None:
    class Fetcher:
        def fetch_many(self, _cells, *, article_date):
            return [
                KosisValue(100.0, "SUCCESS", "a" * 64, "API"),
                KosisValue(0.0, "SUCCESS", "b" * 64, "API"),
            ]

    verdict = verify_claim_against_kosis(
        _claim(),
        _concept(),
        [_candidate()],
        article_date=date(2025, 1, 16),
        official_fetcher=Fetcher(),
    )

    assert verdict.route_status == "HOLD"
    assert verdict.reason_code == "CALCULATION_FAILED"
