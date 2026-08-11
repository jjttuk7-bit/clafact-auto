from datetime import date

from core.data_loader import SemanticStandardRecord
from core.dynamic_e2e_batch_runner import run_dynamic_e2e_batch
from schemas.candidate import KosisCandidateSchema
from schemas.claim import ClaimSchema
from schemas.claim_registry import ClaimRegistryRecord


def _employment_record() -> ClaimRegistryRecord:
    return ClaimRegistryRecord(
        article_id="A1", sentence_id="S1", article_published_at=date(2025, 1, 15), source_ref="test",
        claim=ClaimSchema(
            claim_id="C1", source_sentence="2024년 12월 취업자 수는 2,804만1천 명이었다.",
            indicator="취업자 수", value=28_041_000, unit="명", time="2024년 12월",
            frequency="월", region="한국", parse_status="AUTO_OK",
        ),
    )


def _employment_concept() -> list[SemanticStandardRecord]:
    return [SemanticStandardRecord(
        concept_id="employment_count", canonical_name="취업자 수", standard_key="employment_count",
        aliases=("취업자 수",),
    )]


def _employment_candidate() -> KosisCandidateSchema:
    return KosisCandidateSchema(
        org_id="101", tbl_id="DT_1DA7028S", tbl_name="성/종사상지위별 취업자",
        core_item_ids=["T30"], core_item_names=["취업자"], dimension_ids=["B", "J"],
        dimension_names=["성별", "종사상지위"], dimension_members={"B": ["계"], "J": ["계"]},
        dimension_member_codes={"B": {"계": "0"}, "J": {"계": "00"}},
        unit_names=["천명"], frequency="월", metadata_status="OFFICIAL_METADATA_READY",
    )


def test_dynamic_batch_verifies_structured_employment_claim_without_profile() -> None:
    results = run_dynamic_e2e_batch(
        [_employment_record()], _employment_concept(), [_employment_candidate()],
        api_lookup=lambda _cell: [{
            "TBL_ID": "DT_1DA7028S", "ITM_ID": "T30", "PRD_DE": "202412",
            "B": "0", "J": "00", "DT": "28041", "LST_CHN_DE": "2025-01-10",
        }],
    )

    assert results[0]["route_status"] == "AUTO"
    assert results[0]["verdict"] == "MATCH"
    assert results[0]["profile_id"] is None
    assert results[0]["calculated_value"] == 28_041_000


def test_dynamic_batch_uses_live_catalog_when_local_catalog_has_no_candidate() -> None:
    class LiveSearch:
        def __init__(self) -> None:
            self.queries: list[str] = []

        def search(self, query: str) -> list[KosisCandidateSchema]:
            self.queries.append(query)
            return [_employment_candidate()]

    live = LiveSearch()
    results = run_dynamic_e2e_batch(
        [_employment_record(), _employment_record()], _employment_concept(), [],
        live_search=live, api_lookup=lambda _cell: [{
            "TBL_ID": "DT_1DA7028S", "ITM_ID": "T30", "PRD_DE": "202412",
            "B": "0", "J": "00", "DT": "28041", "LST_CHN_DE": "2025-01-10",
        }],
    )

    assert live.queries == ["취업자 수"]
    assert results[0]["route_status"] == "AUTO"


def test_dynamic_batch_caches_official_metadata_by_table(monkeypatch) -> None:
    calls: list[tuple[str, str]] = []

    def fake_get_meta(_key: str, org_id: str, table_id: str, **_kwargs: object) -> list[dict[str, object]]:
        calls.append((org_id, table_id))
        return []

    monkeypatch.setattr("core.dynamic_e2e_batch_runner.get_meta", fake_get_meta)
    run_dynamic_e2e_batch(
        [_employment_record(), _employment_record()], _employment_concept(), [_employment_candidate()],
        kosis_api_key="test-key",
        api_lookup=lambda _cell: [],
    )

    assert calls == [("101", "DT_1DA7028S")]


def test_dynamic_batch_caches_official_values_by_evidence_coordinate() -> None:
    calls: list[str] = []

    def lookup(cell):
        calls.append(cell.canonical_key)
        return [{
            "TBL_ID": "DT_1DA7028S", "ITM_ID": "T30", "PRD_DE": "202412",
            "B": "0", "J": "00", "DT": "28041", "LST_CHN_DE": "2025-01-10",
        }]

    run_dynamic_e2e_batch(
        [_employment_record(), _employment_record()], _employment_concept(), [_employment_candidate()],
        api_lookup=lookup,
    )

    assert len(calls) == 1


def test_dynamic_batch_records_claim_parse_hold_in_execution_trace() -> None:
    record = _employment_record().model_copy(update={
        "claim": _employment_record().claim.model_copy(update={"parse_status": "HUMAN_REVIEW", "parse_reason": "SLOT_AMBIGUOUS"})
    })

    result = run_dynamic_e2e_batch([record], _employment_concept(), [_employment_candidate()])[0]

    assert result["route_status"] == "HOLD"
    assert result["reason_code"] == "SLOT_AMBIGUOUS"
    assert result["execution_trace"]["events"] == [{
        "stage": "CLAIM_PARSE", "status": "HOLD", "reason_code": "SLOT_AMBIGUOUS", "output_ref": None,
    }]


def test_dynamic_batch_reparses_non_auto_claim_before_semantic_mapping() -> None:
    original = _employment_record().model_copy(update={
        "claim": _employment_record().claim.model_copy(update={"parse_status": "HOLD", "parse_reason": "OLD_PARSE_HOLD"})
    })
    reparsed: list[str] = []

    def reparse(claim, _article_date):
        reparsed.append(claim.claim_id)
        return claim.model_copy(update={"parse_status": "AUTO_OK", "parse_reason": None})

    result = run_dynamic_e2e_batch(
        [original], _employment_concept(), [_employment_candidate()],
        claim_reparser=reparse,
        api_lookup=lambda _cell: [{
            "TBL_ID": "DT_1DA7028S", "ITM_ID": "T30", "PRD_DE": "202412",
            "B": "0", "J": "00", "DT": "28041", "LST_CHN_DE": "2025-01-10",
        }],
    )[0]

    assert reparsed == ["C1"]
    assert result["route_status"] == "AUTO"
