from datetime import date

from core.dynamic_kosis_verifier import verify_claim_against_kosis
from core.kosis_fetcher import KosisValue, OfficialValueFetcher
from core.kosis_publication import KosisPublicationLookup, PublicationEvidence
from schemas.candidate import KosisCandidateSchema
from schemas.claim import ClaimSchema
from schemas.concept import StandardConceptSchema
from schemas.evidence import EvidenceCellSchema
from tools.run_record_comparison_group import _csv_row


class _Response:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self) -> bytes:
        return self.payload


def test_exact_schedule_date_cannot_replace_requested_period_release() -> None:
    explanation = (
        '[{"statsNm":"Employment Survey","pubDate":"2025-01-01",'
        '"publictMth":"https://kostat.go.kr/board.es?act=view&list_no=1"}]'
    ).encode()
    wrong_release = (
        "<h1>2024년 12월 고용동향</h1><span>게시일 2025-01-01</span>"
    ).encode("utf-8")
    requested: list[str] = []

    def opener(request, *, timeout):
        requested.append(request.full_url)
        return _Response(wrong_release if "kostat.go.kr" in request.full_url else explanation)

    result = KosisPublicationLookup("secret", opener=opener, retries=1).fetch(
        "101", "DT", period="2025-06"
    )

    assert len(requested) >= 2
    assert result.status == "UNRESOLVED"
    assert result.published_at is None


def _cells() -> list[EvidenceCellSchema]:
    return [
        EvidenceCellSchema(
            org_id="101", tbl_id="DT", itm_id="T", dimension_codes={"C1": "00"},
            prd_se="M", prd_de=period, unit="%", canonical_key=period, status="CONFIRMED",
        )
        for period in ("2024-06", "2025-06")
    ]


def test_unplanned_continuous_range_row_is_also_checked_for_late_change() -> None:
    rows = [
        {"TBL_ID": "DT", "ITM_ID": "T", "PRD_DE": "202406", "DT": "60", "LST_CHN_DE": "2024-07-01"},
        {"TBL_ID": "DT", "ITM_ID": "T", "PRD_DE": "202407", "DT": "61", "LST_CHN_DE": "2025-07-17"},
        {"TBL_ID": "DT", "ITM_ID": "T", "PRD_DE": "202506", "DT": "70", "LST_CHN_DE": "2025-07-03"},
    ]

    class Api:
        def fetch_many(self, _cells):
            return rows

    class Publication:
        def fetch(self, _org, _table, *, period):
            return PublicationEvidence(
                status="VERIFIED", published_at=date(2025, 7, 16),
                source_url="https://kostat.go.kr/release", content_hash="a" * 64,
                reference_period=period,
            )

    values = OfficialValueFetcher(
        [], api_lookup=Api(), prefer_api=True, publication_lookup=Publication(),
        require_verified_release_metadata=True,
    ).fetch_record_history(_cells(), article_date=date(2025, 7, 16))

    assert {value.status for value in values} == {"AS_OF_UNAVAILABLE"}


def _record_claim() -> ClaimSchema:
    return ClaimSchema(
        claim_id="strict-required", source_sentence="수출액은 2024년 30억원으로 역대 최대였다.",
        indicator="수출액", value=30, unit="억원", time="2024년", frequency="년",
        calculation="RECORD_HIGH", comparison={"type": "RECORD_HIGH"}, parse_status="AUTO_OK",
    )


def test_record_claim_holds_when_fetcher_lacks_strict_range_capability() -> None:
    class GenericOnly:
        calls = 0

        def fetch_many(self, cells, *, article_date):
            self.calls += 1
            return [KosisValue(value, "SUCCESS", "hash", "API") for value in (10, 20, 30)]

    fetcher = GenericOnly()
    concept = StandardConceptSchema(
        concept_id="export", canonical_name="수출액", standard_key="export",
        matched_alias="수출액", status="MATCHED",
    )
    candidate = KosisCandidateSchema(
        org_id="101", tbl_id="DT", tbl_name="수출액", core_item_ids=["T"],
        core_item_names=["수출액"], unit_names=["억원"], item_units={"T": "억원"},
        frequency="년", start_period="2022", end_period="2025",
        metadata_status="OFFICIAL_METADATA_READY",
    )

    verdict = verify_claim_against_kosis(
        _record_claim(), concept, [candidate], article_date=date(2025, 1, 2),
        official_fetcher=fetcher,
    )

    assert fetcher.calls == 0
    assert verdict.route_status == "HOLD"
    assert verdict.reason_code == "FETCH_FAILED"


def test_csv_preserves_release_url_hash_and_retrieval_time() -> None:
    row = _csv_row({
        "claim": {"calculation": "RECORD_HIGH"},
        "official_resolution": {"verdict": {
            "evidence_cells": [{"prd_de": "2025-06"}],
            "official_value_provenance": [{
                "source": "API", "content_hash": "range-hash",
                "publication": {
                    "status": "VERIFIED", "source_url": "https://kostat.go.kr/release",
                    "content_hash": "release-hash", "retrieved_at": "2026-08-23T00:00:00Z",
                },
            }],
        }},
    })

    assert row["publication_source_urls"] == "https://kostat.go.kr/release"
    assert row["publication_hashes"] == "release-hash"
    assert row["publication_retrieved_at"] == "2026-08-23T00:00:00Z"
