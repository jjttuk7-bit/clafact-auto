from core.kosis_catalog_adapter import OfficialTableStructure
from schemas.candidate import KosisCandidateSchema


def test_refresh_uses_kosis_itm_metadata_with_api_key() -> None:
    from core.catalog_metadata_refresh import refresh_item_metadata

    candidate = KosisCandidateSchema(org_id='101', tbl_id='DT', tbl_name='고용', metadata_status='STRUCTURAL_READY')
    refreshed = refresh_item_metadata(
        [candidate],
        'secret',
        metadata_fetcher=lambda api_key, org_id, table_id, *, meta_type, retries, timeout_seconds: [
            {'ORG_ID': org_id, 'TBL_ID': table_id, 'OBJ_ID': 'C1', 'OBJ_NM': '지역', 'ITM_ID': 'T1', 'ITM_NM': '고용률', 'UNIT_NM': '%'},
        ],
    )

    assert refreshed[0].core_item_ids == ['T1']
    assert refreshed[0].dimension_ids == ['C1']


def test_refresh_keeps_candidates_unchanged_without_api_key() -> None:
    from core.catalog_metadata_refresh import refresh_item_metadata

    candidate = KosisCandidateSchema(org_id='101', tbl_id='DT', tbl_name='고용', metadata_status='STRUCTURAL_READY')
    assert refresh_item_metadata([candidate], None) == [candidate]

def test_refresh_hydrates_dimension_member_codes_from_official_itm_metadata() -> None:
    from core.catalog_metadata_refresh import refresh_item_metadata

    candidate = KosisCandidateSchema(org_id="101", tbl_id="DT", tbl_name="고용", metadata_status="STRUCTURAL_READY")
    refreshed = refresh_item_metadata(
        [candidate],
        "secret",
        metadata_fetcher=lambda api_key, org_id, table_id, *, meta_type, retries, timeout_seconds: [
            {"ORG_ID": org_id, "TBL_ID": table_id, "OBJ_ID": "ITEM", "OBJ_NM": "항목", "ITM_ID": "T30", "ITM_NM": "취업자", "UNIT_NM": "천명"},
            {"ORG_ID": org_id, "TBL_ID": table_id, "OBJ_ID": "B", "OBJ_NM": "성별", "ITM_ID": "0", "ITM_NM": "계"},
            {"ORG_ID": org_id, "TBL_ID": table_id, "OBJ_ID": "J", "OBJ_NM": "종사상지위", "ITM_ID": "00", "ITM_NM": "계"},
        ],
    )

    assert refreshed[0].dimension_members == {"B": ["계"], "J": ["계"]}
    assert refreshed[0].dimension_member_codes == {"B": {"계": "0"}, "J": {"계": "00"}}

def test_refresh_combines_official_item_and_period_metadata() -> None:
    from core.catalog_metadata_refresh import refresh_item_metadata

    def fetcher(api_key, org_id, table_id, *, meta_type, retries, timeout_seconds):
        if meta_type == "PRD":
            return [{"PRD_SE": "월", "STRT_PRD_DE": "1975.01", "END_PRD_DE": "2026.07"}]
        return [
            {"ORG_ID": org_id, "TBL_ID": table_id, "OBJ_ID": "ITEM", "OBJ_NM": "항목", "ITM_ID": "T", "ITM_NM": "소비자물가지수", "UNIT_NM": "2020=100"},
            {"ORG_ID": org_id, "TBL_ID": table_id, "OBJ_ID": "I", "OBJ_NM": "품목별", "ITM_ID": "B01", "ITM_NM": "가공식품"},
        ]

    refreshed = refresh_item_metadata(
        [KosisCandidateSchema(org_id="101", tbl_id="DT_CPI", tbl_name="품목별 소비자물가지수", metadata_status="LIVE_SEARCH_UNRESOLVED")],
        "secret", metadata_fetcher=fetcher,
    )[0]

    assert refreshed.frequency == "월"
    assert refreshed.start_period == "1975.01"
    assert refreshed.end_period == "2026.07"
    assert refreshed.dimension_member_codes == {"I": {"가공식품": "B01"}}


def test_refresh_infers_period_frequency_from_official_period_format_when_label_is_mojibake() -> None:
    from core.catalog_metadata_refresh import refresh_item_metadata

    def fetcher(api_key, org_id, table_id, *, meta_type, retries, timeout_seconds):
        if meta_type == "PRD":
            return [
                {"PRD_SE": "Пљ", "STRT_PRD_DE": "1975.01", "END_PRD_DE": "2026.07"},
                {"PRD_SE": "КаБт", "STRT_PRD_DE": "1975 1/4", "END_PRD_DE": "2026 2/4"},
                {"PRD_SE": "Гт", "STRT_PRD_DE": "1975", "END_PRD_DE": "2025"},
            ]
        return [{"ORG_ID": org_id, "TBL_ID": table_id, "OBJ_ID": "ITEM", "OBJ_NM": "항목", "ITM_ID": "T", "ITM_NM": "소비자물가지수", "UNIT_NM": "2020=100"}]

    refreshed = refresh_item_metadata(
        [KosisCandidateSchema(org_id="101", tbl_id="DT_CPI", tbl_name="소비자물가지수", metadata_status="LIVE_SEARCH_UNRESOLVED")],
        "secret", metadata_fetcher=fetcher,
    )[0]

    assert refreshed.frequency == "월|분기|년"
    assert refreshed.metadata_status == "OFFICIAL_METADATA_READY"


def test_period_metadata_never_upgrades_candidate_without_official_item_metadata() -> None:
    from core.catalog_metadata_refresh import refresh_item_metadata

    def fetcher(api_key, org_id, table_id, *, meta_type, retries, timeout_seconds):
        if meta_type == "PRD":
            return [{"PRD_SE": "M", "STRT_PRD_DE": "1975.01", "END_PRD_DE": "2026.07"}]
        raise RuntimeError("ITM unavailable")

    refreshed = refresh_item_metadata(
        [KosisCandidateSchema(org_id="101", tbl_id="DT_CPI", tbl_name="CPI", metadata_status="LIVE_SEARCH_UNRESOLVED")],
        "secret", metadata_fetcher=fetcher,
    )[0]

    assert refreshed.frequency is None
    assert refreshed.metadata_status == "OFFICIAL_ITEM_METADATA_UNAVAILABLE"


def test_refresh_respects_candidate_metadata_budget_and_preserves_unfetched_rows() -> None:
    from core.catalog_metadata_refresh import refresh_item_metadata

    calls: list[tuple[str, str]] = []

    def fetcher(api_key, org_id, table_id, *, meta_type, retries, timeout_seconds):
        calls.append((table_id, meta_type))
        if meta_type == "PRD":
            return [{"PRD_SE": "년", "STRT_PRD_DE": "2020", "END_PRD_DE": "2024"}]
        return [{
            "ORG_ID": org_id, "TBL_ID": table_id, "OBJ_ID": "ITEM",
            "OBJ_NM": "항목", "ITM_ID": "T", "ITM_NM": "수출액", "UNIT_NM": "천$",
        }]

    candidates = [
        KosisCandidateSchema(org_id="145", tbl_id=f"DT_{index}", tbl_name=str(index), metadata_status="LIVE_SEARCH_UNRESOLVED")
        for index in range(3)
    ]

    refreshed = refresh_item_metadata(
        candidates, "secret", metadata_fetcher=fetcher, max_candidates=1,
    )

    assert calls == [("DT_0", "ITM"), ("DT_0", "PRD")]
    assert refreshed[0].metadata_status == "OFFICIAL_METADATA_READY"
    assert refreshed[1:] == candidates[1:]


def test_period_metadata_failure_is_preserved_as_unavailable() -> None:
    from core.catalog_metadata_refresh import refresh_item_metadata

    def fetcher(api_key, org_id, table_id, *, meta_type, retries, timeout_seconds):
        if meta_type == "PRD":
            raise RuntimeError("PRD unavailable")
        return [{
            "ORG_ID": org_id, "TBL_ID": table_id, "OBJ_ID": "ITEM",
            "OBJ_NM": "항목", "ITM_ID": "T", "ITM_NM": "소비자물가지수",
            "UNIT_NM": "2020=100",
        }]

    refreshed = refresh_item_metadata(
        [KosisCandidateSchema(
            org_id="101", tbl_id="DT_CPI", tbl_name="CPI",
            metadata_status="LIVE_SEARCH_UNRESOLVED",
        )],
        "secret", metadata_fetcher=fetcher,
    )[0]

    assert refreshed.metadata_status == "OFFICIAL_PERIOD_METADATA_UNAVAILABLE"


def test_empty_period_metadata_is_preserved_as_unavailable() -> None:
    from core.catalog_metadata_refresh import refresh_item_metadata

    def fetcher(api_key, org_id, table_id, *, meta_type, retries, timeout_seconds):
        if meta_type == "PRD":
            return []
        return [{
            "ORG_ID": org_id, "TBL_ID": table_id, "OBJ_ID": "ITEM",
            "OBJ_NM": "항목", "ITM_ID": "T", "ITM_NM": "소비자물가지수",
            "UNIT_NM": "2020=100",
        }]

    refreshed = refresh_item_metadata(
        [KosisCandidateSchema(
            org_id="101", tbl_id="DT_CPI", tbl_name="CPI",
            metadata_status="LIVE_SEARCH_UNRESOLVED",
        )],
        "secret", metadata_fetcher=fetcher,
    )[0]

    assert refreshed.metadata_status == "OFFICIAL_PERIOD_METADATA_UNAVAILABLE"

def test_refresh_default_budget_limits_live_metadata_requests_to_eight_candidates() -> None:
    from core.catalog_metadata_refresh import refresh_item_metadata

    calls: list[tuple[str, str]] = []

    def fetcher(api_key, org_id, table_id, *, meta_type, retries, timeout_seconds):
        calls.append((table_id, meta_type))
        if meta_type == "PRD":
            return [{"PRD_SE": "년", "STRT_PRD_DE": "2020", "END_PRD_DE": "2024"}]
        return [{
            "ORG_ID": org_id, "TBL_ID": table_id, "OBJ_ID": "ITEM",
            "OBJ_NM": "항목", "ITM_ID": "T", "ITM_NM": "수출액", "UNIT_NM": "천$",
        }]

    candidates = [
        KosisCandidateSchema(org_id="145", tbl_id=f"DT_{index}", tbl_name=str(index), metadata_status="LIVE_SEARCH_UNRESOLVED")
        for index in range(9)
    ]

    refreshed = refresh_item_metadata(candidates, "secret", metadata_fetcher=fetcher)

    assert len(calls) == 16
    assert refreshed[7].metadata_status == "OFFICIAL_METADATA_READY"
    assert refreshed[8] == candidates[8]


def test_refresh_passes_configured_request_retry_and_timeout_budget() -> None:
    from core.catalog_metadata_refresh import refresh_item_metadata

    request_budgets: list[tuple[int, int]] = []

    def fetcher(api_key, org_id, table_id, *, meta_type, retries, timeout_seconds):
        request_budgets.append((retries, timeout_seconds))
        return []

    candidate = KosisCandidateSchema(
        org_id="145",
        tbl_id="DT_EXPORT",
        tbl_name="수출액",
        metadata_status="LIVE_SEARCH_UNRESOLVED",
    )

    refresh_item_metadata(
        [candidate],
        "secret",
        metadata_fetcher=fetcher,
        retries=1,
        timeout_seconds=10,
    )

    assert request_budgets == [(1, 10)]
