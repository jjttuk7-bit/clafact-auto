from core.catalog_discovery import build_catalog_discovery_queries, discover_catalog_candidates, has_unresolved_live_metadata, rank_discovered_candidates
from core.kosis_live_catalog import KosisLiveCatalogSearch
from schemas.candidate import KosisCandidateSchema
from schemas.claim import ClaimSchema
from schemas.concept import StandardConceptSchema


def _claim() -> ClaimSchema:
    return ClaimSchema(claim_id="c", source_sentence="원문에는 쓰지 않을 검색어", indicator="가공식품 물가", value=3.5, unit="%", parse_status="AUTO_OK")


def _concept() -> StandardConceptSchema:
    return StandardConceptSchema(concept_id="c", canonical_name="가공식품 물가", standard_key="processed_food", status="MATCHED")


def test_discovery_queries_structured_indicator_only_when_local_is_empty() -> None:
    queries: list[str] = []

    class Search:
        def search(self, query: str):
            queries.append(query)
            return []

    assert discover_catalog_candidates(_claim(), _concept(), [], Search()) == []  # type: ignore[arg-type]
    assert queries == ["가공식품 물가"]


def test_discovery_preserves_local_structural_candidate_without_live_request() -> None:
    local = KosisCandidateSchema(
        org_id="101",
        tbl_id="DT_LOCAL",
        tbl_name="로컬",
        core_item_ids=["T"],
        core_item_names=["가공식품 물가"],
        unit_names=["%"],
        metadata_status="OFFICIAL_METADATA_READY",
    )

    class Search:
        def search(self, query: str):
            raise AssertionError("live search should not run")

    assert discover_catalog_candidates(_claim(), _concept(), [local], Search()) == [local]  # type: ignore[arg-type]


def test_discovery_expands_live_search_when_local_candidates_miss_claim_dimension() -> None:
    queries: list[str] = []
    claim = _claim().model_copy(
        update={
            "indicator": "수출액",
            "dimension": {"상품": "중고차"},
            "calculation": "GROWTH_RATE",
        }
    )
    concept = _concept().model_copy(
        update={
            "canonical_name": "수출액",
            "kosis_search_terms": ["수출입총괄", "수출금액"],
        }
    )
    local = KosisCandidateSchema(
        org_id="101",
        tbl_id="DT_GENERIC_EXPORT",
        tbl_name="수출입총괄",
        metadata_status="STRUCTURAL_READY",
    )
    live = KosisCandidateSchema(
        org_id="145",
        tbl_id="DT_USED_CAR_EXPORT",
        tbl_name="중고차 수출액",
        metadata_status="LIVE_SEARCH_UNRESOLVED",
    )

    class Search:
        def search(self, query: str):
            queries.append(query)
            return [live] if query == "중고차 수출액" else []

    result = discover_catalog_candidates(claim, concept, [local], Search())  # type: ignore[arg-type]

    assert queries[0] == "중고차 수출액"
    assert [candidate.tbl_id for candidate in result] == [
        "DT_USED_CAR_EXPORT",
        "DT_GENERIC_EXPORT",
    ]


def test_discovery_keeps_dimension_compatible_local_candidate_without_live_request() -> None:
    claim = _claim().model_copy(
        update={
            "indicator": "수출액",
            "dimension": {"상품": "중고차"},
            "calculation": "GROWTH_RATE",
        }
    )
    concept = _concept().model_copy(update={"canonical_name": "수출액"})
    local = KosisCandidateSchema(
        org_id="145",
        tbl_id="DT_LOCAL_USED_CAR",
        tbl_name="품목별 수출액",
        dimension_ids=["C1"],
        dimension_names=["상품"],
        dimension_members={"C1": ["중고차", "승용차"]},
        dimension_member_codes={"C1": {"중고차": "USED", "승용차": "CAR"}},
        core_item_ids=["T"],
        core_item_names=["수출액"],
        unit_names=["천달러"],
        metadata_status="OFFICIAL_METADATA_READY",
    )

    class Search:
        def search(self, query: str):
            raise AssertionError("dimension-compatible local metadata should be reused")

    assert discover_catalog_candidates(claim, concept, [local], Search()) == [local]  # type: ignore[arg-type]


def test_unresolved_live_metadata_is_reportable() -> None:
    live = KosisLiveCatalogSearch("key", opener=lambda *_, **__: _Response()).search("물가")[0]
    assert has_unresolved_live_metadata([live]) is True


class _Response:
    def read(self) -> bytes:
        return '[{"ORG_ID":"101","TBL_ID":"DT_LIVE","TBL_NM":"물가지수"}]'.encode('utf-8')

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None


def test_discovery_queries_concept_with_region_population_and_dimension_context() -> None:
    queries: list[str] = []

    class Search:
        def search(self, query: str):
            queries.append(query)
            return []

    claim = _claim().model_copy(update={
        "indicator": "취업자 수",
        "region": "서울",
        "population": "15세 이상",
        "dimension": {"품목": "사과"},
    })
    concept = _concept().model_copy(update={
        "canonical_name": "취업자 수", "matched_alias": "취업자수"
    })

    assert discover_catalog_candidates(claim, concept, [], Search()) == []  # type: ignore[arg-type]
    assert queries == [
        "서울 15세 이상 사과 취업자 수",
        "사과 취업자 수",
        "15세 이상 취업자 수",
        "서울 취업자 수",
        "취업자 수",
    ]


def test_discovery_respects_live_query_budget_in_ranked_query_order() -> None:
    queries: list[str] = []

    class Search:
        def search(self, query: str):
            queries.append(query)
            return []

    claim = _claim().model_copy(
        update={
            "indicator": "수출액",
            "region": "서울",
            "population": "사업체",
            "dimension": {"상품": "중고차"},
        }
    )
    concept = _concept().model_copy(update={"canonical_name": "수출액"})

    discover_catalog_candidates(
        claim,
        concept,
        [],
        Search(),  # type: ignore[arg-type]
        max_live_queries=2,
    )

    assert queries == ["서울 사업체 중고차 수출액", "중고차 수출액"]


def test_discovery_budget_preserves_population_in_combined_query() -> None:
    queries: list[str] = []

    class Search:
        def search(self, query: str):
            queries.append(query)
            return []

    claim = _claim().model_copy(
        update={
            "indicator": "취업자 수",
            "region": "서울",
            "population": "15세 이상",
            "dimension": {"성별": "여자"},
        }
    )
    concept = _concept().model_copy(update={"canonical_name": "취업자 수"})

    discover_catalog_candidates(
        claim,
        concept,
        [],
        Search(),  # type: ignore[arg-type]
        max_live_queries=1,
    )

    assert queries == ["서울 15세 이상 여자 취업자 수"]


def test_discovery_combines_region_population_and_all_dimensions_first() -> None:
    queries: list[str] = []

    class Search:
        def search(self, query: str):
            queries.append(query)
            return []

    claim = _claim().model_copy(
        update={
            "indicator": "취업자 수",
            "region": "서울",
            "population": "15세 이상",
            "dimension": {"성별": "여자", "산업": "제조업"},
        }
    )
    concept = _concept().model_copy(update={"canonical_name": "취업자 수"})

    discover_catalog_candidates(
        claim,
        concept,
        [],
        Search(),  # type: ignore[arg-type]
        max_live_queries=1,
    )

    assert queries == ["서울 15세 이상 여자 제조업 취업자 수"]


def test_discovery_combines_region_and_population_without_dimension_first() -> None:
    queries: list[str] = []

    class Search:
        def search(self, query: str):
            queries.append(query)
            return []

    claim = _claim().model_copy(
        update={
            "indicator": "취업자 수",
            "region": "서울",
            "population": "15세 이상",
            "dimension": None,
        }
    )
    concept = _concept().model_copy(update={"canonical_name": "취업자 수"})

    discover_catalog_candidates(
        claim,
        concept,
        [],
        Search(),  # type: ignore[arg-type]
        max_live_queries=1,
    )

    assert queries == ["서울 15세 이상 취업자 수"]

def test_discovery_uses_concept_kosis_search_terms_before_news_labels() -> None:
    concept = _concept().model_copy(update={
        "canonical_name": "물가상승률",
        "matched_alias": "가공식품 물가",
        "kosis_search_terms": ["소비자물가지수 품목별", "소비자물가지수"],
    })
    queries = build_catalog_discovery_queries(_claim(), concept)

    assert queries[:2] == ["소비자물가지수 품목별", "소비자물가지수"]
    assert "가공식품 물가" in queries


def test_rank_discovered_candidates_prefers_table_matching_official_terms_and_dimension() -> None:
    claim = _claim().model_copy(update={"dimension": {"품목": "가공식품"}})
    concept = _concept().model_copy(update={
        "canonical_name": "물가상승률",
        "kosis_search_terms": ["소비자물가지수 품목별", "소비자물가지수"],
    })
    candidates = [
        KosisCandidateSchema(org_id="101", tbl_id="GENERIC", tbl_name="소비자물가지수", metadata_status="LIVE_SEARCH_UNRESOLVED"),
        KosisCandidateSchema(org_id="101", tbl_id="ITEM", tbl_name="품목별 소비자물가지수", metadata_status="LIVE_SEARCH_UNRESOLVED"),
    ]

    assert [item.tbl_id for item in rank_discovered_candidates(claim, concept, candidates)] == ["ITEM", "GENERIC"]


def test_discovery_prioritizes_raw_dimension_value_before_generic_export_queries() -> None:
    claim = _claim().model_copy(update={
        "indicator": "수출액",
        "dimension": {"raw": '{"품목": ["화장품"]}'},
    })
    concept = _concept().model_copy(update={
        "canonical_name": "수출액",
        "kosis_search_terms": ["수출입총괄", "국가별 수출액 수입액", "수출금액"],
    })

    queries = build_catalog_discovery_queries(claim, concept)

    assert queries[0] == "화장품 수출액"
    assert queries.index("화장품 수출입총괄") < queries.index("수출입총괄")


def test_rank_uses_unwrapped_raw_dimension_values() -> None:
    claim = _claim().model_copy(update={"dimension": {"raw": '{"품목": ["화장품"]}'}})
    concept = _concept().model_copy(update={
        "canonical_name": "수출액",
        "kosis_search_terms": ["수출입총괄"],
    })
    candidates = [
        KosisCandidateSchema(org_id="360", tbl_id="A_GENERIC", tbl_name="수출액 현황", metadata_status="LIVE_SEARCH_UNRESOLVED"),
        KosisCandidateSchema(org_id="145", tbl_id="Z_COSMETICS", tbl_name="화장품 수출액 현황", metadata_status="LIVE_SEARCH_UNRESOLVED"),
    ]

    ranked = rank_discovered_candidates(claim, concept, candidates)

    assert [candidate.tbl_id for candidate in ranked] == ["Z_COSMETICS", "A_GENERIC"]

def test_discovery_uses_claim_indicator_before_unresolved_concept_placeholders() -> None:
    claim = _claim().model_copy(
        update={
            "indicator": "중고차 수출액",
            "dimension": {"상품": "중고차"},
        }
    )
    concept = _concept().model_copy(
        update={
            "concept_id": "UNRESOLVED",
            "canonical_name": "UNRESOLVED",
            "standard_key": "unresolved",
            "matched_alias": None,
            "kosis_search_terms": [],
            "status": "UNRESOLVED",
        }
    )

    queries = build_catalog_discovery_queries(claim, concept)

    assert queries[0] == "중고차 수출액"
    assert all("UNRESOLVED" not in query for query in queries)
    assert "중고차 중고차 수출액" not in queries
