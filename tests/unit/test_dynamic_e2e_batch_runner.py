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
    assert "profile_id" not in results[0]
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
    calls: list[tuple[str, str, str]] = []

    def fake_get_meta(_key: str, org_id: str, table_id: str, **kwargs: object) -> list[dict[str, object]]:
        calls.append((org_id, table_id, str(kwargs["meta_type"])))
        return []

    monkeypatch.setattr("core.dynamic_e2e_batch_runner.get_meta", fake_get_meta)
    run_dynamic_e2e_batch(
        [_employment_record(), _employment_record()], _employment_concept(), [_employment_candidate()],
        kosis_api_key="test-key",
        api_lookup=lambda _cell: [],
    )

    assert calls == [("101", "DT_1DA7028S", "ITM"), ("101", "DT_1DA7028S", "PRD")]


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


def test_dynamic_batch_normalizes_freeform_parse_detail_to_stable_reason_code() -> None:
    detail = "한 문장에 수출액과 수입액이라는 서로 독립적인 두 수치가 포함됨"
    record = _employment_record().model_copy(update={
        "claim": _employment_record().claim.model_copy(update={
            "parse_status": "HOLD",
            "parse_reason": detail,
        })
    })

    result = run_dynamic_e2e_batch([record], _employment_concept(), [])[0]

    assert result["reason_code"] == "MULTIPLE_CLAIMS"
    assert result["parse_reason_detail"] == detail


def test_dynamic_batch_enriches_explicit_growth_contract_before_slot_quality() -> None:
    claim = _employment_record().claim.model_copy(update={
        "source_sentence": "2024년 취업자 수는 전년 대비 2.1% 증가했다.",
        "value": 2.1,
        "unit": "%",
        "time": "2024",
        "frequency": "년",
        "comparison": {"reference_period": "전년"},
        "calculation": "GROWTH_RATE",
        "condition": None,
    })
    record = _employment_record().model_copy(update={"claim": claim})

    result = run_dynamic_e2e_batch([record], _employment_concept(), [])[0]

    assert result["reason_code"] != "CLAIM_PARSE_UNCERTAIN"


def test_dynamic_batch_holds_invalid_auto_contract_before_catalog_search() -> None:
    record = _employment_record().model_copy(update={
        "claim": _employment_record().claim.model_copy(update={
            "value": 3.1,
            "unit": "%",
            "calculation": "GROWTH_RATE",
            "comparison": {"type": "YEAR_OVER_YEAR"},
            "condition": None,
        })
    })

    class FailingLiveSearch:
        def search(self, _query: str) -> list[KosisCandidateSchema]:
            raise AssertionError("contract HOLD must occur before catalog search")

    result = run_dynamic_e2e_batch(
        [record], _employment_concept(), [], live_search=FailingLiveSearch()
    )[0]

    assert result["route_status"] == "HOLD"
    assert result["reason_code"] == "MISSING_REQUIRED_SLOTS:condition"
    assert result["claim_contract"]["missing_slots"] == ["condition"]

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


def test_dynamic_batch_uses_frozen_discovery_snapshot_and_records_its_hash() -> None:
    from core.kosis_discovery_snapshot import DiscoverySnapshot

    snapshot = DiscoverySnapshot.empty("gold-v1")
    snapshot.record_candidates("취업자 수", [_employment_candidate()])
    from core.evidence_resolver import resolve_evidence_cell
    cell = resolve_evidence_cell(_employment_record().claim, _employment_candidate())
    snapshot.record_value_rows(cell.canonical_key, [{
        "TBL_ID": "DT_1DA7028S", "ITM_ID": "T30", "PRD_DE": "202412",
        "B": "0", "J": "00", "DT": "28041", "LST_CHN_DE": "2025-01-10",
    }])

    class FailingLiveSearch:
        def search(self, _query: str):
            raise AssertionError("frozen snapshot must prevent live catalog access")

    result = run_dynamic_e2e_batch(
        [_employment_record()], _employment_concept(), [],
        live_search=FailingLiveSearch(),
        discovery_snapshot=snapshot,
        api_lookup=lambda _cell: [{
            "TBL_ID": "DT_1DA7028S", "ITM_ID": "T30", "PRD_DE": "202412",
            "B": "0", "J": "00", "DT": "28041", "LST_CHN_DE": "2025-01-10",
        }],
    )[0]

    assert result["route_status"] == "AUTO"
    assert result["kosis_discovery_snapshot_hash"] == snapshot.content_hash


def test_dynamic_batch_falls_back_to_live_catalog_when_local_candidates_fail_hard_guard() -> None:
    wrong_local = _employment_candidate().model_copy(update={"tbl_id": "DT_ANNUAL", "frequency": "년"})

    class LiveSearch:
        def __init__(self) -> None:
            self.queries: list[str] = []
        def search(self, query: str) -> list[KosisCandidateSchema]:
            self.queries.append(query)
            return [_employment_candidate()]

    live = LiveSearch()
    result = run_dynamic_e2e_batch(
        [_employment_record()], _employment_concept(), [wrong_local],
        live_search=live,
        api_lookup=lambda _cell: [{
            "TBL_ID": "DT_1DA7028S", "ITM_ID": "T30", "PRD_DE": "202412",
            "B": "0", "J": "00", "DT": "28041", "LST_CHN_DE": "2025-01-10",
        }],
    )[0]

    assert live.queries == ["취업자 수"]
    assert result["route_status"] == "AUTO"


def test_dynamic_batch_records_final_snapshot_hash_after_refresh() -> None:
    from core.kosis_discovery_snapshot import DiscoverySnapshot

    snapshot = DiscoverySnapshot.empty("gold-v1")

    class LiveSearch:
        def search(self, _query: str) -> list[KosisCandidateSchema]:
            return [_employment_candidate()]

    result = run_dynamic_e2e_batch(
        [_employment_record()], _employment_concept(), [],
        live_search=LiveSearch(),
        discovery_snapshot=snapshot,
        refresh_discovery_snapshot=True,
        api_lookup=lambda _cell: [{
            "TBL_ID": "DT_1DA7028S", "ITM_ID": "T30", "PRD_DE": "202412",
            "B": "0", "J": "00", "DT": "28041", "LST_CHN_DE": "2025-01-10",
        }],
    )[0]

    assert result["route_status"] == "AUTO"
    assert result["kosis_discovery_snapshot_hash"] == snapshot.content_hash


def test_dynamic_batch_holds_flattened_indicator_before_catalog_search() -> None:
    record = _employment_record().model_copy(update={
        "claim": _employment_record().claim.model_copy(update={
            "source_sentence": "지난달 가공식품 물가는 전년 동월 대비 3.1% 올랐다.",
            "indicator": "물가상승률",
            "value": 3.1,
        })
    })

    class FailingLiveSearch:
        def search(self, _query: str) -> list[KosisCandidateSchema]:
            raise AssertionError("slot-quality HOLD must occur before catalog search")

    result = run_dynamic_e2e_batch(
        [record], _employment_concept(), [], live_search=FailingLiveSearch()
    )[0]

    assert result["route_status"] == "HOLD"
    assert result["reason_code"] == "CLAIM_PARSE_UNCERTAIN"
    assert result["execution_trace"]["events"][-1]["stage"] == "CLAIM_PARSE"
    assert result["slot_quality"]["detected_modifier"] == "가공식품"


def test_dynamic_batch_hydrates_candidate_from_read_only_snapshot_without_api_key() -> None:
    from core.evidence_resolver import resolve_evidence_cell
    from core.kosis_discovery_snapshot import DiscoverySnapshot

    snapshot = DiscoverySnapshot.empty("gold-v1")
    unresolved = KosisCandidateSchema(
        org_id="101", tbl_id="DT_1DA7028S", tbl_name="성/종사상지위별 취업자",
        metadata_status="LIVE_SEARCH_UNRESOLVED",
    )
    snapshot.record_candidates("취업자 수", [unresolved])
    snapshot.record_metadata("101", "DT_1DA7028S", [
        {
            "ORG_ID": "101", "TBL_ID": "DT_1DA7028S", "OBJ_ID": "ITEM",
            "OBJ_NM": "항목", "ITM_ID": "T30", "ITM_NM": "취업자", "UNIT_NM": "천명",
        },
        {
            "ORG_ID": "101", "TBL_ID": "DT_1DA7028S", "OBJ_ID": "B",
            "OBJ_NM": "성별", "ITM_ID": "0", "ITM_NM": "계",
        },
        {
            "ORG_ID": "101", "TBL_ID": "DT_1DA7028S", "OBJ_ID": "J",
            "OBJ_NM": "종사상지위", "ITM_ID": "00", "ITM_NM": "계",
        },
    ], meta_type="ITM")
    snapshot.record_metadata("101", "DT_1DA7028S", [
        {"PRD_SE": "월", "STRT_PRD_DE": "2000.01", "END_PRD_DE": "2025.12"},
    ], meta_type="PRD")
    cell = resolve_evidence_cell(_employment_record().claim, _employment_candidate())
    snapshot.record_value_rows(cell.canonical_key, [{
        "TBL_ID": "DT_1DA7028S", "ITM_ID": "T30", "PRD_DE": "202412",
        "B": "0", "J": "00", "DT": "28041", "LST_CHN_DE": "2025-01-10",
    }])

    result = run_dynamic_e2e_batch(
        [_employment_record()], _employment_concept(), [],
        discovery_snapshot=snapshot,
    )[0]

    assert result["route_status"] == "AUTO"
    assert result["evidence_cells"][0]["dimension_codes"] == {"B": "0", "J": "00"}


def test_dynamic_batch_uses_verified_live_search_terms_even_when_local_candidate_passes_guard() -> None:
    export_record = ClaimRegistryRecord(
        article_id="A_EXPORT", sentence_id="19", article_published_at=date(2025, 2, 12), source_ref="test",
        claim=ClaimSchema(
            claim_id="C_EXPORT", source_sentence="지난해 수출은 전년 대비 8.2% 증가했다.",
            indicator="수출액", value=8.2, unit="%", time="2024", frequency="년",
            comparison={"type": "YEAR_OVER_YEAR"}, calculation="GROWTH_RATE",
            condition={"direction": "INCREASE"}, parse_status="AUTO_OK",
        ),
    )
    concept = [SemanticStandardRecord(
        concept_id="export_value", canonical_name="수출액", standard_key="export_value",
        aliases=("수출액",), kosis_search_terms=("수출입총괄",),
    )]
    local_cosmetics = KosisCandidateSchema(
        org_id="145", tbl_id="DT_COSMETICS", tbl_name="화장품 수입 및 수출액 현황",
        core_item_ids=["T002"], core_item_names=["수출액"], dimension_ids=["13999000"],
        dimension_names=["가상분류"], dimension_members={"13999000": ["데이터"]},
        dimension_member_codes={"13999000": {"데이터": "DATA"}},
        unit_names=["천불"], frequency="년", metadata_status="OFFICIAL_METADATA_READY",
    )
    official_total = local_cosmetics.model_copy(update={
        "org_id": "134", "tbl_id": "DT_134001_001", "tbl_name": "수출입총괄",
        "core_item_names": ["수출금액"], "frequency": "월|년",
    })

    class LiveSearch:
        def __init__(self) -> None:
            self.queries: list[str] = []
        def search(self, query: str) -> list[KosisCandidateSchema]:
            self.queries.append(query)
            return [official_total] if query == "수출입총괄" else []

    live = LiveSearch()
    result = run_dynamic_e2e_batch(
        [export_record], concept, [local_cosmetics], live_search=live,
        api_lookup=lambda cell: [{
            "TBL_ID": cell.tbl_id, "ITM_ID": cell.itm_id, "PRD_DE": cell.prd_de,
            "DT": "108.2" if cell.prd_de == "2024" else "100", "LST_CHN_DE": "2025-01-02",
        }],
    )[0]

    assert live.queries[0] == "수출입총괄"
    assert result["route_status"] == "AUTO"
    assert result["evidence_cells"][0]["tbl_id"] == "DT_134001_001"
