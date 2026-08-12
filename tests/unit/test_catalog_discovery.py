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
    local = KosisCandidateSchema(org_id="101", tbl_id="DT_LOCAL", tbl_name="로컬", metadata_status="STRUCTURAL_READY")

    class Search:
        def search(self, query: str):
            raise AssertionError("live search should not run")

    assert discover_catalog_candidates(_claim(), _concept(), [local], Search()) == [local]  # type: ignore[arg-type]


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
    assert queries == ["서울 취업자 수", "15세 이상 취업자 수", "사과 취업자 수", "취업자 수"]

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