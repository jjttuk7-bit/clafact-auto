from core.catalog_discovery import discover_catalog_candidates, has_unresolved_live_metadata
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
    assert queries == ["취업자 수", "취업자 수 서울", "취업자 수 15세 이상", "취업자 수 사과"]