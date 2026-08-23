from datetime import date

from core.kosis_fetcher import KosisValue
from core.official_evidence_service import OfficialEvidenceService
from core.unified_claim_pipeline import verify_registry_record
from schemas.candidate import KosisCandidateSchema
from schemas.claim import ClaimSchema
from schemas.claim_registry import ClaimRegistryRecord
from schemas.concept import StandardConceptSchema


class _UnusedExtractor:
    def extract(self, source_sentence: str, **kwargs):
        raise AssertionError("record comparison split must reuse the grounded stored Claim")


class _OfficialFetcher:
    def __init__(self) -> None:
        self.single_periods: list[str] = []
        self.batch_calls: list[list[str]] = []
        self.values = {"2022": 1000.0, "2023": 1300.0, "2024": 1419.0}

    def fetch(self, cell, *, article_date):
        assert article_date == date(2025, 1, 2)
        self.single_periods.append(cell.prd_de)
        return self._value(cell.prd_de)

    def fetch_many(self, cells, *, article_date):
        assert article_date == date(2025, 1, 2)
        self.batch_calls.append([cell.prd_de for cell in cells])
        return [self._value(cell.prd_de) for cell in cells]

    def fetch_record_history(self, cells, *, article_date):
        return self.fetch_many(cells, article_date=article_date)

    def _value(self, period: str) -> KosisValue:
        return KosisValue(
            self.values[period], "SUCCESS", f"hash-{period}", "API",
            source_url="https://kosis.kr/openapi", retrieved_at="2025-01-02T00:00:00Z",
        )


def test_record_claim_splits_and_both_children_finish_the_unified_official_pipeline() -> None:
    claim = ClaimSchema(
        claim_id="parent-record",
        source_sentence="\ubc18\ub3c4\uccb4 \uc218\ucd9c\uc561\uc774 1419\uc5b5\ub2ec\ub7ec\ub85c \uc5ed\ub300 \ucd5c\ub300\uce58\ub97c \uae30\ub85d\ud588\ub2e4.",
        indicator="\ubc18\ub3c4\uccb4 \uc218\ucd9c\uc561", value=1419, unit="\uc5b5\ub2ec\ub7ec",
        time="2024\ub144", frequency="\ub144", dimension={"\ud488\ubaa9": "\ubc18\ub3c4\uccb4"},
        calculation="DIRECT_VALUE", comparison={"type": "RECORD_HIGH"},
        parse_status="HOLD", parse_reason="RECORD_COMPARISON_REQUIRES_SEPARATE_CLAIM",
    )
    record = ClaimRegistryRecord(
        article_id="A1", sentence_id="1", claim=claim,
        article_published_at=date(2025, 1, 2), source_ref="integration-test",
    )
    concept = StandardConceptSchema(
        concept_id="semiconductor_export", canonical_name="\ubc18\ub3c4\uccb4 \uc218\ucd9c\uc561",
        standard_key="semiconductor_export", matched_alias="\ubc18\ub3c4\uccb4 \uc218\ucd9c\uc561", status="MATCHED",
    )
    candidate = KosisCandidateSchema(
        org_id="101", tbl_id="DT_EXP", tbl_name="\ud488\ubaa9\ubcc4 \uc218\ucd9c\uc561",
        core_item_ids=["T"], core_item_names=["\uc218\ucd9c\uc561"],
        dimension_ids=["C1"], dimension_names=["\ud488\ubaa9"],
        dimension_members={"C1": ["\ubc18\ub3c4\uccb4"]},
        dimension_member_codes={"C1": {"\ubc18\ub3c4\uccb4": "S"}},
        unit_names=["\uc5b5\ub2ec\ub7ec"], item_units={"T": "\uc5b5\ub2ec\ub7ec"},
        frequency="\ub144", start_period="2022", end_period="2025",
        metadata_status="OFFICIAL_METADATA_READY",
    )
    fetcher = _OfficialFetcher()
    service = OfficialEvidenceService(
        concept_mapper=lambda _: concept,
        catalog_resolver=lambda *_: [candidate],
        official_fetcher=fetcher,
    )

    entries = verify_registry_record(
        record, extractor=_UnusedExtractor(), official_service=service,
    )

    assert len(entries) == 2
    assert [entry.claim.calculation for entry in entries] == ["DIRECT_VALUE", "RECORD_HIGH"]
    assert all(entry.parent_claim_id == "parent-record" for entry in entries)
    assert all(entry.recovery_action == "RECORD_COMPARISON_SPLIT" for entry in entries)
    assert all(entry.admission_route == "KOSIS_PIPELINE_ELIGIBLE" for entry in entries)
    assert fetcher.batch_calls == [["2024"], ["2022", "2023", "2024"]]
    assert [entry.official_resolution.verdict.reason_code for entry in entries] == [
        "WITHIN_TOLERANCE", "RECORD_CONFIRMED",
    ]
    assert all(entry.official_resolution.verdict.execution_trace is not None for entry in entries)
    assert all(entry.stage_results[0].stage == "CLAIM_SPLIT" for entry in entries)
