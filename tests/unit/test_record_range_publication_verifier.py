from datetime import date

from core.dynamic_kosis_verifier import verify_claim_against_kosis
from core.kosis_fetcher import KosisValue
from schemas.candidate import KosisCandidateSchema
from schemas.claim import ClaimSchema
from schemas.concept import StandardConceptSchema


def _claim(calculation: str = "RECORD_HIGH") -> ClaimSchema:
    return ClaimSchema(
        claim_id="record-routing",
        source_sentence="수출액은 2024년 30억원으로 역대 최대였다.",
        indicator="수출액",
        value=30,
        unit="억원",
        time="2024년",
        frequency="년",
        calculation=calculation,
        comparison={"type": calculation} if calculation == "RECORD_HIGH" else None,
        parse_status="AUTO_OK",
    )


def _concept() -> StandardConceptSchema:
    return StandardConceptSchema(
        concept_id="export",
        canonical_name="수출액",
        standard_key="export",
        matched_alias="수출액",
        status="MATCHED",
    )


def _candidate() -> KosisCandidateSchema:
    return KosisCandidateSchema(
        org_id="101",
        tbl_id="DT_EXPORT",
        tbl_name="수출액",
        core_item_ids=["T"],
        core_item_names=["수출액"],
        unit_names=["억원"],
        item_units={"T": "억원"},
        frequency="년",
        start_period="2022",
        end_period="2025",
        metadata_status="OFFICIAL_METADATA_READY",
    )


class RoutingFetcher:
    def __init__(self, *, record_status: str = "SUCCESS") -> None:
        self.record_status = record_status
        self.record_calls = 0
        self.batch_calls = 0

    def fetch_record_history(self, cells, *, article_date):
        self.record_calls += 1
        assert article_date == date(2025, 1, 2)
        return [
            KosisValue(
                value if self.record_status == "SUCCESS" else None,
                self.record_status,
                f"hash-{cell.prd_de}",
                "API",
            )
            for cell, value in zip(cells, (10, 20, 30), strict=True)
        ]

    def fetch_many(self, cells, *, article_date):
        self.batch_calls += 1
        return [KosisValue(30, "SUCCESS", "direct", "API") for _ in cells]


def test_record_claim_uses_strict_record_history_path() -> None:
    fetcher = RoutingFetcher()
    verdict = verify_claim_against_kosis(
        _claim(),
        _concept(),
        [_candidate()],
        article_date=date(2025, 1, 2),
        official_fetcher=fetcher,
    )
    assert fetcher.record_calls == 1
    assert fetcher.batch_calls == 0
    assert verdict.reason_code == "RECORD_CONFIRMED"


def test_record_history_failure_is_not_retried_through_weaker_batch_path() -> None:
    fetcher = RoutingFetcher(record_status="AS_OF_UNAVAILABLE")
    verdict = verify_claim_against_kosis(
        _claim(),
        _concept(),
        [_candidate()],
        article_date=date(2025, 1, 2),
        official_fetcher=fetcher,
    )
    assert fetcher.record_calls == 1
    assert fetcher.batch_calls == 0
    assert verdict.route_status == "HOLD"
    assert verdict.reason_code == "AS_OF_UNAVAILABLE"


def test_non_record_claim_keeps_existing_batch_path() -> None:
    fetcher = RoutingFetcher()
    verdict = verify_claim_against_kosis(
        _claim("DIRECT_VALUE").model_copy(update={"source_sentence": "수출액은 2024년 30억원이었다."}),
        _concept(),
        [_candidate()],
        article_date=date(2025, 1, 2),
        official_fetcher=fetcher,
    )
    assert fetcher.record_calls == 0
    assert fetcher.batch_calls == 1
    assert verdict.route_status == "AUTO"
