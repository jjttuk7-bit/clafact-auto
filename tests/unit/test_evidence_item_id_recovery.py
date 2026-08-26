from core.evidence_resolver_impl import resolve_evidence_cell
from schemas.candidate import KosisCandidateSchema
from schemas.claim import ClaimSchema


def _claim() -> ClaimSchema:
    return ClaimSchema(
        claim_id="export", source_sentence="2025년 1월 수출액은 100억달러다.",
        indicator="수출액", value=10_000_000_000, unit="달러",
        time="2025-01", frequency="월", calculation="DIRECT_VALUE",
        parse_status="AUTO_OK",
    )


def _candidate(**updates) -> KosisCandidateSchema:
    candidate = KosisCandidateSchema(
        org_id="360", tbl_id="TRADE", tbl_name="품목별 수출액, 수입액",
        core_item_ids=[], core_item_names=["수출액", "수입액"],
        unit_names=["천달러"], item_units={"T1": "천달러", "T2": "천달러"},
        frequency="월", start_period="2000.01", end_period="2026.12",
        metadata_status="OFFICIAL_METADATA_READY",
    )
    return candidate.model_copy(update=updates)


def test_recovers_official_item_ids_from_ordered_item_unit_metadata() -> None:
    evidence = resolve_evidence_cell(_claim(), _candidate())
    assert evidence.status == "CONFIRMED"
    assert evidence.itm_id == "T1"
    assert evidence.unit == "천달러"


def test_does_not_infer_item_ids_when_metadata_cardinality_differs() -> None:
    evidence = resolve_evidence_cell(
        _claim(), _candidate(item_units={"T1": "천달러"})
    )
    assert evidence.status == "UNRESOLVED"
