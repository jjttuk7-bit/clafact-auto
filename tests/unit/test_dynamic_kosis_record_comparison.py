from datetime import date

from core.dynamic_kosis_verifier import verify_claim_against_kosis
from core.kosis_fetcher import KosisValue
from schemas.candidate import KosisCandidateSchema
from schemas.claim import ClaimSchema
from schemas.concept import StandardConceptSchema


def _claim(value: float = 1419) -> ClaimSchema:
    return ClaimSchema(
        claim_id="record",
        source_sentence="\ubc18\ub3c4\uccb4 \uc218\ucd9c\uc561\uc740 1419\uc5b5\ub2ec\ub7ec\ub85c \uc5ed\ub300 \ucd5c\ub300\uc600\ub2e4.",
        indicator="\ubc18\ub3c4\uccb4 \uc218\ucd9c\uc561", value=value, unit="\uc5b5\ub2ec\ub7ec",
        time="2024\ub144", frequency="\ub144", dimension={"\ud488\ubaa9": "\ubc18\ub3c4\uccb4"},
        calculation="RECORD_HIGH", comparison={"type": "RECORD_HIGH"},
        parse_status="AUTO_OK",
    )


def _concept() -> StandardConceptSchema:
    return StandardConceptSchema(
        concept_id="semiconductor_export", canonical_name="\ubc18\ub3c4\uccb4 \uc218\ucd9c\uc561",
        standard_key="semiconductor_export", matched_alias="\ubc18\ub3c4\uccb4 \uc218\ucd9c\uc561", status="MATCHED",
    )


def _candidate() -> KosisCandidateSchema:
    return KosisCandidateSchema(
        org_id="101", tbl_id="DT_EXP", tbl_name="\ud488\ubaa9\ubcc4 \uc218\ucd9c\uc561",
        core_item_ids=["T"], core_item_names=["\uc218\ucd9c\uc561"],
        dimension_ids=["C1"], dimension_names=["\ud488\ubaa9"],
        dimension_members={"C1": ["\ubc18\ub3c4\uccb4"]},
        dimension_member_codes={"C1": {"\ubc18\ub3c4\uccb4": "S"}},
        unit_names=["\uc5b5\ub2ec\ub7ec"], item_units={"T": "\uc5b5\ub2ec\ub7ec"},
        frequency="\ub144", start_period="2022", end_period="2025",
        metadata_status="OFFICIAL_METADATA_READY",
    )


class _Fetcher:
    def __init__(self, values: dict[str, KosisValue]) -> None:
        self.values = values
        self.periods: list[str] = []

    def fetch_many(self, cells, *, article_date):
        assert article_date == date(2025, 1, 2)
        self.periods = [cell.prd_de for cell in cells]
        return [self.values[cell.prd_de] for cell in cells]


def _value(value: float | None, status: str = "SUCCESS") -> KosisValue:
    return KosisValue(value, status, f"hash-{value}", "API", source_url="https://kosis.kr/openapi", retrieved_at="2025-01-02T00:00:00Z")


def test_record_high_fetches_complete_history_and_records_tied_periods() -> None:
    fetcher = _Fetcher({"2022": _value(1000), "2023": _value(1419), "2024": _value(1419)})

    verdict = verify_claim_against_kosis(
        _claim(), _concept(), [_candidate()],
        article_date=date(2025, 1, 2), official_fetcher=fetcher,
    )

    assert fetcher.periods == ["2022", "2023", "2024"]
    assert verdict.route_status == "AUTO"
    assert verdict.verdict == "MATCH"
    assert verdict.reason_code == "RECORD_CONFIRMED"
    assert verdict.record_comparison is not None
    assert verdict.record_comparison.start_period == "2022"
    assert verdict.record_comparison.end_period == "2024"
    assert verdict.record_comparison.observed_count == 3
    assert verdict.record_comparison.record_value == 1419
    assert verdict.record_comparison.record_periods == ["2023", "2024"]
    assert len(verdict.official_value_provenance) == 3


def test_record_high_mismatches_when_current_value_is_below_historical_maximum() -> None:
    fetcher = _Fetcher({"2022": _value(1000), "2023": _value(1419), "2024": _value(1300)})

    verdict = verify_claim_against_kosis(
        _claim(1300), _concept(), [_candidate()],
        article_date=date(2025, 1, 2), official_fetcher=fetcher,
    )

    assert verdict.route_status == "AUTO"
    assert verdict.verdict == "MISMATCH"
    assert verdict.reason_code == "RECORD_NOT_CONFIRMED"


def test_official_record_comparison_does_not_use_article_rounding_tolerance() -> None:
    claim = _claim(2.2).model_copy(update={
        "source_sentence": "\uc218\ucd9c\uc561\uc740 2.2%\ub85c \uc5ed\ub300 \ucd5c\ub300\uc600\ub2e4.",
        "unit": "%",
    })
    candidate = _candidate().model_copy(update={
        "unit_names": ["%"], "item_units": {"T": "%"},
    })
    fetcher = _Fetcher({"2022": _value(2.24), "2023": _value(2.1), "2024": _value(2.2)})

    verdict = verify_claim_against_kosis(
        claim, _concept(), [candidate],
        article_date=date(2025, 1, 2), official_fetcher=fetcher,
    )

    assert verdict.verdict == "MISMATCH"
    assert verdict.reason_code == "RECORD_NOT_CONFIRMED"


def test_record_high_holds_when_any_historical_value_is_missing() -> None:
    fetcher = _Fetcher({"2022": _value(1000), "2023": _value(None, "NO_DATA"), "2024": _value(1419)})

    verdict = verify_claim_against_kosis(
        _claim(), _concept(), [_candidate()],
        article_date=date(2025, 1, 2), official_fetcher=fetcher,
    )

    assert verdict.route_status == "HOLD"
    assert verdict.reason_code == "NO_DATA"
    assert verdict.record_comparison is None
